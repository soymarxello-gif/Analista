package com.analista.mobile.data

import com.analista.mobile.domain.BacktestEngine
import com.analista.mobile.domain.CanonicalAnalysisEngine
import com.analista.mobile.domain.DataQualityEngine
import com.analista.mobile.domain.DecisionOverlayEngine
import com.analista.mobile.domain.FinalDecisionPersistenceFactory
import com.analista.mobile.domain.LiveReproducibilityAssembler
import com.analista.mobile.domain.TechnicalEngine
import com.analista.mobile.domain.TradePlanGenerationEngine
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.UUID
import kotlin.math.round

private data class ScanWorkItem(
    val analyzed: AnalyzedCandidate,
    val bars: List<PriceBar>,
    val dataQualityStatus: String,
    val executionDataAllowed: Boolean,
    val cacheHit: Boolean,
    val retries: Int,
    val retrievedAtUtc: Long
)

class ScanRepository(
    private val dao: AnalistaDao,
    private val yahoo: YahooFinanceClient,
    private val marketData: MarketDataGateway,
    private val tickers: List<String> = DEFAULT_TICKERS,
    private val datasetCapture: RunDatasetCaptureService? = null
) {
    suspend fun runScan(): ScanRunEntity = coroutineScope {
        val started = System.currentTimeMillis()
        val semaphore = Semaphore(4)
        var failures = 0
        var cacheHits = 0
        var retries = 0
        var lowQualityCount = 0
        var unusableQualityCount = 0
        val quoteBatch = marketData.quotes(tickers)
        val quoteFailures = tickers.count { quoteBatch.quotes[it] == null }
        val workItems = tickers.map { ticker ->
            async {
                runCatching {
                    semaphore.withPermit {
                        val fetched = yahoo.dailyHistory(ticker)
                        val retrievedAtUtc = System.currentTimeMillis()
                        val quality = DataQualityEngine.assess(fetched.bars, fetched.cacheHit, started)
                        synchronized(this@ScanRepository) {
                            if (fetched.cacheHit) cacheHits += 1
                            retries += fetched.retries
                            if (quality.status == "LOW") lowQualityCount += 1
                            if (quality.status == "UNUSABLE") unusableQualityCount += 1
                        }
                        val quote = quoteBatch.quotes[ticker]
                        ScanWorkItem(
                            analyzed = TechnicalEngine.analyzeWithAnalysis(
                                ticker,
                                fetched.bars,
                                TradeContext(
                                    quote = quote,
                                    marketCap = quote?.marketCap,
                                    quoteType = quote?.quoteType,
                                    dataQualityStatus = quality.status,
                                    dataQualityScore = quality.score,
                                    dataQualityReasons = quality.reasons,
                                    averageDollarVolume20 = quality.averageDollarVolume20,
                                    sessionsOld = quality.sessionsOld,
                                    executionDataAllowed = quality.executionAllowed
                                )
                            ),
                            bars = fetched.bars,
                            dataQualityStatus = quality.status,
                            executionDataAllowed = quality.executionAllowed,
                            cacheHit = fetched.cacheHit,
                            retries = fetched.retries,
                            retrievedAtUtc = retrievedAtUtc
                        )
                    }
                }.onFailure { synchronized(this@ScanRepository) { failures += 1 } }.getOrNull()
            }
        }.awaitAll().filterNotNull().sortedByDescending { it.analyzed.candidate.score }
        val analyzed = workItems.map { it.analyzed }
        val barsByTicker = workItems.associate { it.analyzed.candidate.ticker to it.bars }
        val workItemsByTicker = workItems.associateBy { it.analyzed.candidate.ticker }

        val runId = DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss").withZone(ZoneId.of("UTC"))
            .format(Instant.ofEpochMilli(started)) + "-" + UUID.randomUUID().toString().take(8)
        val manifests = if (workItems.isEmpty()) {
            emptyList()
        } else {
            LiveReproducibilityAssembler.assemble(
                runId = runId,
                universe = tickers,
                inputs = workItems.map { item ->
                    LiveReproducibilityAssembler.TickerInput(
                        ticker = item.analyzed.candidate.ticker,
                        bars = item.bars,
                        dataQualityStatus = item.dataQualityStatus,
                        cacheHit = item.cacheHit,
                        retries = item.retries,
                        retrievedAtUtc = item.retrievedAtUtc
                    )
                }
            )
        }
        val marketDate = LocalDate.now(ZoneId.of("America/New_York")).toString()
        val alpacaDegraded = quoteBatch.alpacaStatus !in setOf("AVAILABLE", "NOT_CONFIGURED")
        val trust = when {
            analyzed.isEmpty() -> "UNUSABLE"
            failures > tickers.size / 2 || unusableQualityCount > tickers.size / 2 -> "UNUSABLE"
            failures > 0 || cacheHits > 0 || quoteFailures > 0 || lowQualityCount > 0 ||
                unusableQualityCount > 0 || alpacaDegraded || quoteBatch.divergenceCount > 0 -> "DEGRADED"
            else -> "TRUSTED"
        }
        val finished = System.currentTimeMillis()
        val sourceDescription = buildString {
            append(quoteBatch.primarySource)
            quoteBatch.feed?.let { append("/").append(it) }
            if (quoteBatch.fallbackCount > 0) append(" + fallback(").append(quoteBatch.fallbackCount).append(")")
            if (quoteBatch.divergenceCount > 0) append(" + divergence(").append(quoteBatch.divergenceCount).append(")")
            if (cacheHits > 0) append(" + cache(").append(cacheHits).append(")")
            if (lowQualityCount > 0) append(" + quality-low(").append(lowQualityCount).append(")")
            if (unusableQualityCount > 0) append(" + quality-unusable(").append(unusableQualityCount).append(")")
        }
        val run = ScanRunEntity(
            runId = runId, startedAtUtc = started, finishedAtUtc = finished,
            marketDateEt = marketDate,
            status = if (analyzed.isEmpty()) "FAILED_DATA_SOURCE" else "COMPLETED",
            trustStatus = trust, candidateCount = analyzed.size, failureCount = failures + quoteFailures,
            source = sourceDescription,
            durationMs = finished - started, cacheHitCount = cacheHits, retryCount = retries
        )
        val rows = analyzed.map { item ->
            val it = item.candidate
            CandidateEntity(
                runId = runId, ticker = it.ticker, signal = it.signal, score = it.score,
                close = it.close, sma20 = it.sma20, sma50 = it.sma50, rsi14 = it.rsi14,
                macd = it.macd, macdSignal = it.macdSignal, stochastic = it.stochastic,
                atr14 = it.atr14, relativeVolume = it.relativeVolume, entry = it.entry,
                stop = it.stop, target = it.target, rr = it.rr, reason = it.reason,
                quoteStatus = it.quoteStatus, executionQuoteQuality = it.executionQuoteQuality,
                triggerConfirmed = it.triggerConfirmed, setupType = it.setupType,
                allVetoReasons = it.allVetoReasons.joinToString(","),
                penaltyReasons = it.penaltyReasons.joinToString(","),
                actionableEntry = it.actionableEntry, actionableStop = it.actionableStop,
                actionableTarget = it.actionableTarget, theoreticalEntry = it.theoreticalEntry,
                theoreticalStop = it.theoreticalStop, theoreticalTarget = it.theoreticalTarget,
                referenceClose = it.referenceClose, livePremarketPrice = it.livePremarketPrice,
                bid = it.bid, ask = it.ask, spreadPct = it.spreadPct,
                openingGapPct = it.openingGapPct, plannedTrigger = it.plannedTrigger,
                maximumEntry = it.maximumEntry, actionabilityAtExecution = it.actionabilityAtExecution,
                quoteCapturedAtUtc = it.quoteCapturedAtUtc
            )
        }
        val snapshots = fetchMacro(runId, semaphore)
        val enrichment = fetchEnrichment(runId, rows, semaphore)
        val enrichmentByTicker = enrichment.associateBy { it.ticker }
        val engineVersion = "${CanonicalAnalysisEngine.ENGINE_VERSION}+${DecisionOverlayEngine.ENGINE_VERSION}+${TradePlanGenerationEngine.ENGINE_VERSION}"
        val overlaysByTicker = analyzed.associate { item ->
            val candidate = item.candidate
            candidate.ticker to DecisionOverlayEngine.apply(
                candidate,
                item.analysis,
                snapshots,
                enrichmentByTicker[candidate.ticker]
            )
        }
        val analysisRows = analyzed.map { item ->
            val candidate = item.candidate
            val a = item.analysis
            val overlay = overlaysByTicker.getValue(candidate.ticker)
            CandidateAnalysisEntity(
                analysisId = "$runId-${candidate.ticker}", runId = runId, ticker = candidate.ticker,
                rsi6 = a.rsi6, rsi14Canonical = a.rsi14, rsi6GtRsi14 = a.rsi6 > a.rsi14,
                ema20 = a.ema20, ema50 = a.ema50, ema200 = a.ema200,
                priceVsEma20Pct = round2((candidate.close / a.ema20 - 1.0) * 100.0),
                priceVsEma50Pct = round2((candidate.close / a.ema50 - 1.0) * 100.0),
                priceVsEma200Pct = round2((candidate.close / a.ema200 - 1.0) * 100.0),
                weeklyTrend = a.weeklyTrend, assetQualityScore = a.assetQualityScore,
                setupQualityScore = a.setupQualityScore, contextScore = overlay.contextScore,
                institutionalScore = overlay.institutionalScore, riskScore = a.riskScore,
                finalTradeScore = overlay.finalTradeScore, stopAtrMultiple = a.stopAtrMultiple,
                stopAtrStatus = a.stopAtrStatus, scoreBreakdown = overlay.breakdown,
                engineVersion = engineVersion,
                calculatedAtUtc = System.currentTimeMillis()
            )
        }
        val analysisByTicker = analysisRows.associateBy { it.ticker }
        val spyBars = runCatching { yahoo.dailyHistory("SPY", "1y").bars }.getOrNull()
        val generatedPlans = TradePlanGenerationEngine.generate(
            analyzed.mapNotNull { item ->
                val candidate = item.candidate
                val bars = barsByTicker[candidate.ticker] ?: return@mapNotNull null
                val analysis = analysisByTicker[candidate.ticker] ?: return@mapNotNull null
                if (bars.size < 60 || candidate.atr14 <= 0.0) return@mapNotNull null
                val plannedEntry = candidate.actionableEntry
                    ?: candidate.plannedTrigger
                    ?: candidate.theoreticalEntry
                    ?: candidate.close
                TradePlanGenerationEngine.Input(
                    ticker = candidate.ticker,
                    signal = candidate.signal,
                    setupType = candidate.setupType,
                    legacyScore = candidate.score,
                    finalTradeScore = analysis.finalTradeScore,
                    bars = bars,
                    benchmarkBars = spyBars,
                    entry = plannedEntry,
                    atr = candidate.atr14,
                    sma20 = candidate.sma20
                )
            }
        )
        val tradePlans = generatedPlans.map { generated ->
            val s = generated.structure
            val rs = generated.relativeStrength
            val p = generated.riskPlan
            CandidateTradePlanEntity(
                planId = "$runId-${generated.ticker}",
                runId = runId,
                ticker = generated.ticker,
                priorResistance = round2(s.priorResistance),
                nextResistance = s.nextResistance?.let(::round2),
                swingLow = round2(s.swingLow),
                closeLocationValue = round2(s.closeLocationValue),
                baseRangeAtr = round2(s.baseRangeAtr),
                volatilityCompression = round2(s.volatilityCompression),
                resistanceTouches = s.resistanceTouches,
                structureScore = round2(s.structureScore),
                rs20VsSpy = rs?.rs20Pct?.let(::round2),
                rs60VsSpy = rs?.rs60Pct?.let(::round2),
                relativeStrengthScore = round2(rs?.score ?: 50.0),
                relativeStrengthStatus = rs?.status ?: "UNAVAILABLE",
                plannedEntry = round2(p.entry),
                structuralStop = round2(p.stop),
                structuralTarget = round2(p.target),
                stopType = p.stopType,
                stopAtrMultiple = round2(p.stopAtrMultiple),
                structuralRr = round2(p.rr),
                riskPct = round2(p.riskPct),
                rewardPct = round2(p.rewardPct),
                shares = p.shares,
                positionValue = round2(p.positionValue),
                riskBudget = round2(p.riskBudget),
                riskPlanValid = p.valid,
                legacyRank = generated.legacyRank,
                tradeRank = generated.tradeRank,
                rankDelta = generated.rankDelta,
                auditedTradeScore = round2(generated.auditedTradeScore),
                reasons = generated.reasons.joinToString(","),
                engineVersion = TradePlanGenerationEngine.ENGINE_VERSION,
                calculatedAtUtc = System.currentTimeMillis()
            )
        }
        val tradePlansByTicker = tradePlans.associateBy { it.ticker }
        val macroConfidence = when {
            snapshots.size >= 6 -> "HIGH"
            snapshots.isEmpty() -> "UNKNOWN"
            else -> "PARTIAL"
        }
        val finalized = analyzed.mapNotNull { item ->
            val candidate = item.candidate
            val plan = tradePlansByTicker[candidate.ticker] ?: return@mapNotNull null
            val analysis = analysisByTicker[candidate.ticker] ?: return@mapNotNull null
            val overlay = overlaysByTicker[candidate.ticker] ?: return@mapNotNull null
            val workItem = workItemsByTicker[candidate.ticker] ?: return@mapNotNull null
            FinalDecisionPersistenceFactory.create(
                runId = runId,
                candidate = candidate,
                analysis = analysis,
                overlay = overlay,
                plan = plan,
                dataQualityAllowsExecution = workItem.executionDataAllowed,
                macroConfidence = macroConfidence,
                decisionTimestampUtc = started,
                calculatedAtUtc = System.currentTimeMillis(),
                engineVersion = engineVersion
            )
        }
        val finalDecisions = finalized.map { it.decision }
        val contracts = finalized.mapNotNull { it.contract }
        val datasetArtifacts = datasetCapture?.capture(
            runId = runId,
            effectiveDate = marketDate,
            tickers = tickers,
            barsByTicker = barsByTicker,
            quotesByTicker = quoteBatch.quotes,
            macroSnapshots = snapshots,
            createdAtUtc = finished
        ).orEmpty()

        dao.saveRun(run, rows, snapshots)
        if (analysisRows.isNotEmpty()) dao.insertAnalysis(analysisRows)
        if (enrichment.isNotEmpty()) dao.insertEnrichment(enrichment)
        if (tradePlans.isNotEmpty()) dao.insertTradePlans(tradePlans)
        if (finalDecisions.isNotEmpty()) dao.insertFinalDecisions(finalDecisions)
        if (manifests.isNotEmpty()) dao.insertReproducibilityManifests(manifests)
        if (datasetArtifacts.isNotEmpty()) dao.insertRunDatasetArtifacts(datasetArtifacts)
        if (contracts.isNotEmpty()) dao.insertSignalContracts(contracts)
        evaluateSignalContracts(barsByTicker)
        updateBacktestOutcomes(runId, rows)
        run
    }

    suspend fun testAlpaca(credentials: AlpacaCredentialsStore.Credentials) = marketData.testAlpacaConnection(credentials)
    fun saveAlpaca(credentials: AlpacaCredentialsStore.Credentials) = marketData.saveAlpacaCredentials(credentials)
    fun clearAlpaca() = marketData.clearAlpacaCredentials()
    fun alpacaCredentials(): AlpacaCredentialsStore.Credentials? = marketData.alpacaCredentials()

    private suspend fun evaluateSignalContracts(barsByTicker: Map<String, List<PriceBar>>) {
        val outcomes = dao.recentSignalContracts().mapNotNull { contract ->
            val bars = barsByTicker[contract.ticker] ?: return@mapNotNull null
            BacktestEngine.evaluate(contract, bars)
        }
        if (outcomes.isNotEmpty()) dao.upsertTradeOutcomes(outcomes)
    }

    private suspend fun fetchMacro(runId: String, semaphore: Semaphore): List<MarketSnapshotEntity> = coroutineScope {
        MACRO_SYMBOLS.map { (symbol, label) ->
            async {
                runCatching {
                    semaphore.withPermit {
                        val bars = yahoo.dailyHistory(symbol, "3mo").bars
                        val latest = bars.last().close
                        val previous = bars.dropLast(1).last().close
                        MarketSnapshotEntity(
                            snapshotId = "$runId-$symbol", runId = runId, symbol = symbol, label = label,
                            close = round2(latest), changePct = round2((latest / previous - 1.0) * 100.0),
                            capturedAtUtc = System.currentTimeMillis()
                        )
                    }
                }.getOrNull()
            }
        }.awaitAll().filterNotNull()
    }

    private suspend fun fetchEnrichment(
        runId: String,
        candidates: List<CandidateEntity>,
        semaphore: Semaphore
    ): List<CandidateEnrichmentEntity> = coroutineScope {
        candidates.map { candidate ->
            async {
                semaphore.withPermit {
                    val fundamentalResult = runCatching { yahoo.fundamentals(candidate.ticker) }
                    val optionsResult = runCatching { yahoo.options(candidate.ticker) }
                    val fundamental = fundamentalResult.getOrNull()
                    val options = optionsResult.getOrNull()
                    val fundamentalFields = listOf(
                        fundamental?.marketCap, fundamental?.trailingPe, fundamental?.priceToSales,
                        fundamental?.epsTrailing, fundamental?.revenueGrowthPct, fundamental?.grossMarginPct,
                        fundamental?.operatingMarginPct, fundamental?.profitMarginPct, fundamental?.debtToEquity
                    ).count { it != null }
                    val optionFields = listOf(options?.putCallOi, options?.nearCallOi, options?.nearPutOi, options?.expiry)
                        .count { it != null }
                    CandidateEnrichmentEntity(
                        enrichmentId = "$runId-${candidate.ticker}", runId = runId, ticker = candidate.ticker,
                        marketCap = fundamental?.marketCap, trailingPe = fundamental?.trailingPe,
                        priceToSales = fundamental?.priceToSales, epsTrailing = fundamental?.epsTrailing,
                        revenueGrowthPct = fundamental?.revenueGrowthPct?.let(::round2),
                        grossMarginPct = fundamental?.grossMarginPct?.let(::round2),
                        operatingMarginPct = fundamental?.operatingMarginPct?.let(::round2),
                        profitMarginPct = fundamental?.profitMarginPct?.let(::round2),
                        debtToEquity = fundamental?.debtToEquity?.let(::round2),
                        optionsPutCallOi = options?.putCallOi?.let(::round2),
                        optionsNearCallOi = options?.nearCallOi, optionsNearPutOi = options?.nearPutOi,
                        optionsExpiry = options?.expiry,
                        fundamentalsStatus = when {
                            fundamentalResult.isFailure -> "ERROR"
                            fundamentalFields == 0 -> "EMPTY"
                            fundamentalFields >= 7 -> "AVAILABLE_COMPLETE"
                            else -> "AVAILABLE_PARTIAL"
                        },
                        optionsStatus = when {
                            optionsResult.isFailure -> "ERROR"
                            optionFields == 0 -> "EMPTY"
                            optionFields == 4 -> "AVAILABLE_COMPLETE"
                            else -> "AVAILABLE_PARTIAL"
                        },
                        capturedAtUtc = System.currentTimeMillis()
                    )
                }
            }
        }.awaitAll()
    }

    private suspend fun updateBacktestOutcomes(currentRunId: String, current: List<CandidateEntity>) {
        val latestByTicker = current.associateBy { it.ticker }
        val outcomes = dao.priorCandidates(currentRunId)
            .distinctBy { it.runId to it.ticker }
            .mapNotNull { prior ->
                val latest = latestByTicker[prior.ticker] ?: return@mapNotNull null
                BacktestOutcomeEntity(
                    outcomeId = "${prior.runId}-${prior.ticker}", sourceRunId = prior.runId,
                    ticker = prior.ticker, signal = prior.signal, sourceClose = prior.close,
                    latestClose = latest.close, returnPct = round2((latest.close / prior.close - 1.0) * 100.0),
                    evaluatedAtUtc = System.currentTimeMillis()
                )
            }
        if (outcomes.isNotEmpty()) dao.insertOutcomes(outcomes)
    }

    fun observeRuns(): Flow<List<ScanRunEntity>> = dao.observeRuns()
    fun observeCandidates(runId: String): Flow<List<CandidateEntity>> = dao.observeCandidates(runId)
    fun observeMarketSnapshots(runId: String): Flow<List<MarketSnapshotEntity>> = dao.observeMarketSnapshots(runId)
    fun observeOutcomes(): Flow<List<BacktestOutcomeEntity>> = dao.observeOutcomes()
    fun observeTradeOutcomes(): Flow<List<TradeOutcomeEntity>> = dao.observeTradeOutcomes()
    fun observeEnrichment(runId: String): Flow<List<CandidateEnrichmentEntity>> = dao.observeEnrichment(runId)
    fun observeAnalysis(runId: String): Flow<List<CandidateAnalysisEntity>> = dao.observeAnalysis(runId)
    fun observeFinalDecisions(runId: String): Flow<List<FinalDecisionEntity>> = dao.observeFinalDecisions(runId)
    fun observeTradePlans(runId: String): Flow<List<CandidateTradePlanEntity>> = dao.observeTradePlans(runId)
    fun observeRunDatasetArtifacts(runId: String): Flow<List<RunDatasetArtifactEntity>> =
        dao.observeRunDatasetArtifacts(runId)
    fun observeReproducibilityManifests(runId: String): Flow<List<ReproducibilityManifestEntity>> =
        dao.observeReproducibilityManifests(runId)

    companion object {
        val DEFAULT_TICKERS = listOf(
            "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA",
            "JPM", "V", "MA", "COST", "LLY", "NFLX", "AMD", "CRM", "ORCL", "PLTR",
            "UBER", "PANW", "CRWD", "NOW", "MU", "QCOM", "INTC", "AMAT", "LRCX",
            "CAT", "GE", "RTX", "XOM", "CVX", "WMT", "HD", "UNH"
        )
        val MACRO_SYMBOLS = listOf(
            "SPY" to "SPY", "QQQ" to "QQQ", "IWM" to "IWM",
            "^TNX" to "US10Y", "^TYX" to "US30Y", "^VIX" to "VIX",
            "DX-Y.NYB" to "DXY", "CL=F" to "WTI", "BTC-USD" to "Bitcoin"
        )
        private fun round2(value: Double) = round(value * 100.0) / 100.0
    }
}
