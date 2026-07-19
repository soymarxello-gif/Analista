package com.analista.mobile.data

import com.analista.mobile.domain.CanonicalAnalysisEngine
import com.analista.mobile.domain.DataQualityEngine
import com.analista.mobile.domain.DecisionOverlayEngine
import com.analista.mobile.domain.TechnicalEngine
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

class ScanRepository(
    private val dao: AnalistaDao,
    private val yahoo: YahooFinanceClient,
    private val marketData: MarketDataGateway,
    private val tickers: List<String> = DEFAULT_TICKERS
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
        val analyzed = tickers.map { ticker ->
            async {
                runCatching {
                    semaphore.withPermit {
                        val fetched = yahoo.dailyHistory(ticker)
                        val quality = DataQualityEngine.assess(fetched.bars, fetched.cacheHit, started)
                        synchronized(this@ScanRepository) {
                            if (fetched.cacheHit) cacheHits += 1
                            retries += fetched.retries
                            if (quality.status == "LOW") lowQualityCount += 1
                            if (quality.status == "UNUSABLE") unusableQualityCount += 1
                        }
                        val quote = quoteBatch.quotes[ticker]
                        TechnicalEngine.analyzeWithAnalysis(
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
                        )
                    }
                }.onFailure { synchronized(this@ScanRepository) { failures += 1 } }.getOrNull()
            }
        }.awaitAll().filterNotNull().sortedByDescending { it.candidate.score }

        val runId = DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss").withZone(ZoneId.of("UTC"))
            .format(Instant.ofEpochMilli(started)) + "-" + UUID.randomUUID().toString().take(8)
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
        val analysisRows = analyzed.map { item ->
            val candidate = item.candidate
            val a = item.analysis
            val overlay = DecisionOverlayEngine.apply(candidate, a, snapshots, enrichmentByTicker[candidate.ticker])
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
                engineVersion = "${CanonicalAnalysisEngine.ENGINE_VERSION}+${DecisionOverlayEngine.ENGINE_VERSION}",
                calculatedAtUtc = System.currentTimeMillis()
            )
        }
        dao.saveRun(run, rows, snapshots)
        if (analysisRows.isNotEmpty()) dao.insertAnalysis(analysisRows)
        if (enrichment.isNotEmpty()) dao.insertEnrichment(enrichment)
        updateBacktestOutcomes(runId, rows)
        run
    }

    suspend fun testAlpaca(credentials: AlpacaCredentialsStore.Credentials) = marketData.testAlpacaConnection(credentials)
    fun saveAlpaca(credentials: AlpacaCredentialsStore.Credentials) = marketData.saveAlpacaCredentials(credentials)
    fun clearAlpaca() = marketData.clearAlpacaCredentials()
    fun alpacaCredentials(): AlpacaCredentialsStore.Credentials? = marketData.alpacaCredentials()

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
    fun observeEnrichment(runId: String): Flow<List<CandidateEnrichmentEntity>> = dao.observeEnrichment(runId)
    fun observeAnalysis(runId: String): Flow<List<CandidateAnalysisEntity>> = dao.observeAnalysis(runId)

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
