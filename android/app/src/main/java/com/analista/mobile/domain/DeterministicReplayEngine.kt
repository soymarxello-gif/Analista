package com.analista.mobile.domain

import com.analista.mobile.data.CandidateAnalysisEntity
import com.analista.mobile.data.CandidateEnrichmentEntity
import com.analista.mobile.data.CandidateEntity
import com.analista.mobile.data.CandidateTradePlanEntity
import com.analista.mobile.data.FinalDecisionEntity
import com.analista.mobile.data.FundamentalMetrics
import com.analista.mobile.data.FundamentalSnapshotEntity
import com.analista.mobile.data.MarketQuote
import com.analista.mobile.data.MarketSnapshotEntity
import com.analista.mobile.data.NormalizedDatasetDecoder
import com.analista.mobile.data.OptionChainSnapshot
import com.analista.mobile.data.PriceBar
import com.analista.mobile.data.ReproducibilityManifestEntity
import com.analista.mobile.data.RunDefinitionEntity
import com.analista.mobile.data.ScanCandidate
import com.analista.mobile.data.ScanRunEntity
import com.analista.mobile.data.TradeContext
import org.json.JSONObject
import kotlin.math.abs
import kotlin.math.round

object DeterministicReplayEngine {
    const val VERSION = "deterministic-replay-1"

    data class DatasetBundle(
        val barsByTicker: Map<String, List<PriceBar>>,
        val quotesByTicker: Map<String, MarketQuote?>,
        val macroSnapshots: List<MarketSnapshotEntity>,
        val macroHistories: Map<String, List<PriceBar>>,
        val fundamentalsByTicker: Map<String, FundamentalSnapshotEntity>,
        val optionsByTicker: Map<String, OptionChainSnapshot>,
        val universe: NormalizedDatasetDecoder.UniverseDataset
    )

    data class StoredRun(
        val run: ScanRunEntity,
        val definition: RunDefinitionEntity,
        val manifests: List<ReproducibilityManifestEntity>,
        val candidates: List<CandidateEntity>,
        val enrichments: List<CandidateEnrichmentEntity>,
        val analyses: List<CandidateAnalysisEntity>,
        val tradePlans: List<CandidateTradePlanEntity>,
        val finalDecisions: List<FinalDecisionEntity>
    )

    data class TickerResult(
        val ticker: String,
        val manifestMatches: Boolean,
        val technicalMatches: Boolean,
        val analysisMatches: Boolean,
        val planMatches: Boolean,
        val decisionMatches: Boolean,
        val reasons: List<String>
    )

    data class Summary(
        val runId: String,
        val status: String,
        val expectedTickers: Int,
        val replayedTickers: Int,
        val fullyMatchedTickers: Int,
        val mismatchedTickers: Int,
        val missingDatasetCount: Int,
        val tickerResults: List<TickerResult>,
        val reasons: List<String>,
        val engineVersion: String = VERSION
    )

    fun replay(stored: StoredRun, datasets: DatasetBundle): Summary {
        validateRunScope(stored)
        val runId = stored.run.runId
        val configuration = parseConfiguration(stored.definition.configurationJson)
        val universe = stored.definition.universeSymbolsCsv.split(',')
            .map(::ticker).filter { it.isNotBlank() }.distinct().sorted()
        val artifactUniverse = datasets.universe.members.map { ticker(it.ticker) }.distinct().sorted()
        val reasons = mutableListOf<String>()
        if (artifactUniverse != universe) reasons += "universe_dataset_mismatch"
        if (stored.definition.universeHash != stored.manifests.map { it.universeHash }.distinct().singleOrNull()) {
            reasons += "definition_universe_hash_mismatch"
        }
        if (stored.definition.configurationHash != stored.manifests.map { it.configurationHash }.distinct().singleOrNull()) {
            reasons += "definition_configuration_hash_mismatch"
        }

        val manifestByTicker = stored.manifests.associateBy { ticker(it.ticker) }
        val originalCandidates = stored.candidates.associateBy { ticker(it.ticker) }
        val originalEnrichment = stored.enrichments.associateBy { ticker(it.ticker) }
        val originalAnalyses = stored.analyses.associateBy { ticker(it.ticker) }
        val originalPlans = stored.tradePlans.associateBy { ticker(it.ticker) }
        val originalDecisions = stored.finalDecisions.associateBy { ticker(it.ticker) }

        val replayed = mutableMapOf<String, ReplayedTicker>()
        var missingDatasetCount = 0
        for (symbol in universe) {
            val bars = datasets.barsByTicker[symbol]
            val manifest = manifestByTicker[symbol]
            val originalCandidate = originalCandidates[symbol]
            if (bars == null || manifest == null || originalCandidate == null) {
                missingDatasetCount += listOf(bars, manifest, originalCandidate).count { it == null }
                continue
            }
            val quality = DataQualityEngine.assess(bars, manifest.cacheHit, stored.run.startedAtUtc)
            val quote = datasets.quotesByTicker[symbol]
            val analyzed = TechnicalEngine.analyzeWithAnalysis(
                ticker = symbol,
                bars = bars,
                context = TradeContext(
                    quote = quote,
                    marketCap = quote?.marketCap,
                    quoteType = quote?.quoteType,
                    dataQualityStatus = quality.status,
                    dataQualityScore = quality.score,
                    dataQualityReasons = quality.reasons,
                    averageDollarVolume20 = quality.averageDollarVolume20,
                    sessionsOld = quality.sessionsOld,
                    executionDataAllowed = quality.executionAllowed,
                    analysisTimestampUtc = stored.run.startedAtUtc,
                    recordUniverseObservation = false
                )
            )
            val fundamental = datasets.fundamentalsByTicker[symbol]
            val overlay = DecisionOverlayEngine.applyResolved(
                candidate = analyzed.candidate,
                base = analyzed.analysis,
                macro = datasets.macroSnapshots,
                inputs = DecisionOverlayEngine.ResolvedInputs(
                    macroHistories = datasets.macroHistories,
                    fundamentalMetrics = fundamental?.toMetrics(),
                    fundamentalAvailable = fundamental != null,
                    fundamentalCapturedAtUtc = fundamental?.capturedAtUtc,
                    optionChain = datasets.optionsByTicker[symbol],
                    legacyEnrichment = originalEnrichment[symbol]
                )
            )
            val analysisEntity = analyzed.toEntity(runId, overlay, stored.run.finishedAtUtc)
            replayed[symbol] = ReplayedTicker(
                bars = bars,
                qualityAllowsExecution = quality.executionAllowed,
                candidate = analyzed.candidate,
                analysis = analysisEntity,
                overlay = overlay
            )
        }

        val spyBars = datasets.macroHistories["SPY"]
        val generatedPlans = TradePlanGenerationEngine.generate(
            replayed.values.map { replay ->
                val candidate = replay.candidate
                TradePlanGenerationEngine.Input(
                    ticker = candidate.ticker,
                    signal = candidate.signal,
                    setupType = candidate.setupType,
                    legacyScore = candidate.score,
                    finalTradeScore = replay.analysis.finalTradeScore,
                    bars = replay.bars,
                    benchmarkBars = spyBars,
                    entry = candidate.actionableEntry
                        ?: candidate.plannedTrigger
                        ?: candidate.theoreticalEntry
                        ?: candidate.close,
                    atr = candidate.atr14,
                    sma20 = candidate.sma20,
                    sma50 = candidate.sma50
                )
            }
        ).associateBy { ticker(it.ticker) }

        val macroConfidence = when {
            datasets.macroSnapshots.size >= 6 -> "HIGH"
            datasets.macroSnapshots.isEmpty() -> "UNKNOWN"
            else -> "PARTIAL"
        }
        val tickerResults = universe.map { symbol ->
            val tickerReasons = mutableListOf<String>()
            val replay = replayed[symbol]
            val manifest = manifestByTicker[symbol]
            val originalCandidate = originalCandidates[symbol]
            val originalAnalysis = originalAnalyses[symbol]
            val originalPlan = originalPlans[symbol]
            val originalDecision = originalDecisions[symbol]
            val generated = generatedPlans[symbol]
            if (replay == null || manifest == null || originalCandidate == null) {
                tickerReasons += "missing_required_replay_input"
                return@map TickerResult(symbol, false, false, false, false, false, tickerReasons)
            }

            val recalculatedManifest = ReproducibilityEngine.createManifest(replay.bars, configuration, universe)
            val manifestMatches = recalculatedManifest.barsHash == manifest.barsHash &&
                recalculatedManifest.configurationHash == manifest.configurationHash &&
                recalculatedManifest.universeHash == manifest.universeHash &&
                recalculatedManifest.manifestHash == manifest.manifestHash
            if (!manifestMatches) tickerReasons += "manifest_mismatch"

            val technicalMatches = candidateMatches(replay.candidate, originalCandidate)
            if (!technicalMatches) tickerReasons += "technical_mismatch"
            val analysisMatches = originalAnalysis != null && analysisMatches(replay.analysis, originalAnalysis)
            if (!analysisMatches) tickerReasons += "analysis_mismatch"

            val replayPlan = generated?.toEntity(runId, stored.run.finishedAtUtc)
            val planMatches = replayPlan != null && originalPlan != null && planMatches(replayPlan, originalPlan)
            if (!planMatches) tickerReasons += "plan_mismatch"

            val replayDecision = if (replayPlan != null) {
                FinalDecisionPersistenceFactory.create(
                    runId = runId,
                    candidate = replay.candidate,
                    analysis = replay.analysis,
                    overlay = replay.overlay,
                    plan = replayPlan,
                    dataQualityAllowsExecution = replay.qualityAllowsExecution,
                    macroConfidence = macroConfidence,
                    decisionTimestampUtc = stored.run.startedAtUtc,
                    calculatedAtUtc = stored.run.finishedAtUtc,
                    engineVersion = replay.analysis.engineVersion
                ).decision
            } else null
            val decisionMatches = replayDecision != null && originalDecision != null &&
                decisionMatches(replayDecision, originalDecision)
            if (!decisionMatches) tickerReasons += "decision_mismatch"

            TickerResult(
                ticker = symbol,
                manifestMatches = manifestMatches,
                technicalMatches = technicalMatches,
                analysisMatches = analysisMatches,
                planMatches = planMatches,
                decisionMatches = decisionMatches,
                reasons = tickerReasons
            )
        }

        val fullyMatched = tickerResults.count {
            it.manifestMatches && it.technicalMatches && it.analysisMatches && it.planMatches && it.decisionMatches
        }
        val mismatched = tickerResults.count { it.reasons.any { reason -> reason.endsWith("mismatch") } }
        if (missingDatasetCount > 0) reasons += "missing_replay_datasets"
        if (mismatched > 0) reasons += "replay_mismatches_detected"
        val status = when {
            reasons.any { it == "definition_universe_hash_mismatch" || it == "definition_configuration_hash_mismatch" } -> "INVALID"
            missingDatasetCount > 0 || replayed.size < universe.size -> "INCOMPLETE"
            mismatched > 0 || reasons.isNotEmpty() -> "MISMATCH"
            else -> "COMPLETE"
        }
        return Summary(
            runId = runId,
            status = status,
            expectedTickers = universe.size,
            replayedTickers = replayed.size,
            fullyMatchedTickers = fullyMatched,
            mismatchedTickers = mismatched,
            missingDatasetCount = missingDatasetCount,
            tickerResults = tickerResults,
            reasons = reasons.distinct()
        )
    }

    private data class ReplayedTicker(
        val bars: List<PriceBar>,
        val qualityAllowsExecution: Boolean,
        val candidate: ScanCandidate,
        val analysis: CandidateAnalysisEntity,
        val overlay: DecisionOverlayEngine.OverlayResult
    )

    private fun validateRunScope(stored: StoredRun) {
        val runId = stored.run.runId
        require(runId.isNotBlank())
        require(stored.definition.runId == runId)
        require(stored.manifests.all { it.runId == runId })
        require(stored.candidates.all { it.runId == runId })
        require(stored.enrichments.all { it.runId == runId })
        require(stored.analyses.all { it.runId == runId })
        require(stored.tradePlans.all { it.runId == runId })
        require(stored.finalDecisions.all { it.runId == runId })
        require(stored.candidates.map { ticker(it.ticker) }.distinct().size == stored.candidates.size)
    }

    private fun parseConfiguration(json: String): Map<String, String> {
        val root = JSONObject(json)
        return root.keys().asSequence().associateWith { root.getString(it) }.toSortedMap()
    }

    private fun com.analista.mobile.data.AnalyzedCandidate.toEntity(
        runId: String,
        overlay: DecisionOverlayEngine.OverlayResult,
        calculatedAtUtc: Long
    ): CandidateAnalysisEntity {
        val candidate = candidate
        val analysis = analysis
        return CandidateAnalysisEntity(
            analysisId = "$runId-${candidate.ticker}",
            runId = runId,
            ticker = candidate.ticker,
            rsi6 = analysis.rsi6,
            rsi14Canonical = analysis.rsi14,
            rsi6GtRsi14 = analysis.rsi6 > analysis.rsi14,
            ema20 = analysis.ema20,
            ema50 = analysis.ema50,
            ema200 = analysis.ema200,
            priceVsEma20Pct = round2((candidate.close / analysis.ema20 - 1.0) * 100.0),
            priceVsEma50Pct = round2((candidate.close / analysis.ema50 - 1.0) * 100.0),
            priceVsEma200Pct = round2((candidate.close / analysis.ema200 - 1.0) * 100.0),
            weeklyTrend = analysis.weeklyTrend,
            assetQualityScore = analysis.assetQualityScore,
            setupQualityScore = analysis.setupQualityScore,
            contextScore = overlay.contextScore,
            institutionalScore = overlay.institutionalScore,
            riskScore = analysis.riskScore,
            finalTradeScore = overlay.finalTradeScore,
            stopAtrMultiple = analysis.stopAtrMultiple,
            stopAtrStatus = analysis.stopAtrStatus,
            scoreBreakdown = overlay.breakdown,
            engineVersion = "${CanonicalAnalysisEngine.ENGINE_VERSION}+${DecisionOverlayEngine.ENGINE_VERSION}+${TradePlanGenerationEngine.ENGINE_VERSION}",
            calculatedAtUtc = calculatedAtUtc
        )
    }

    private fun TradePlanGenerationEngine.Generated.toEntity(
        runId: String,
        calculatedAtUtc: Long
    ): CandidateTradePlanEntity {
        val structure = structure
        val rs = relativeStrength
        val plan = riskPlan
        return CandidateTradePlanEntity(
            planId = "$runId-$ticker",
            runId = runId,
            ticker = ticker,
            priorResistance = round2(structure.priorResistance),
            nextResistance = structure.nextResistance?.let(::round2),
            swingLow = round2(structure.swingLow),
            closeLocationValue = round2(structure.closeLocationValue),
            baseRangeAtr = round2(structure.baseRangeAtr),
            volatilityCompression = round2(structure.volatilityCompression),
            resistanceTouches = structure.resistanceTouches,
            structureScore = round2(structure.structureScore),
            rs20VsSpy = rs?.rs20Pct?.let(::round2),
            rs60VsSpy = rs?.rs60Pct?.let(::round2),
            relativeStrengthScore = round2(rs?.score ?: 50.0),
            relativeStrengthStatus = rs?.status ?: "UNAVAILABLE",
            plannedEntry = round2(plan.entry),
            structuralStop = round2(plan.stop),
            structuralTarget = round2(plan.target),
            stopType = plan.stopType,
            stopAtrMultiple = round2(plan.stopAtrMultiple),
            structuralRr = round2(plan.rr),
            riskPct = round2(plan.riskPct),
            rewardPct = round2(plan.rewardPct),
            shares = plan.shares,
            positionValue = round2(plan.positionValue),
            riskBudget = round2(plan.riskBudget),
            riskPlanValid = plan.valid,
            legacyRank = legacyRank,
            tradeRank = tradeRank,
            rankDelta = rankDelta,
            auditedTradeScore = round2(auditedTradeScore),
            reasons = reasons.joinToString(","),
            engineVersion = TradePlanGenerationEngine.ENGINE_VERSION,
            calculatedAtUtc = calculatedAtUtc
        )
    }

    private fun FundamentalSnapshotEntity.toMetrics() = FundamentalMetrics(
        marketCap = null,
        trailingPe = null,
        priceToSales = priceToSales,
        epsTrailing = null,
        revenueGrowthPct = revenueYoyPct,
        grossMarginPct = grossMarginPct,
        operatingMarginPct = operatingMarginPct,
        profitMarginPct = netMarginPct,
        debtToEquity = debtToEquity,
        revenueYoyPct = revenueYoyPct,
        revenueTrend = revenueTrend,
        epsYoyPct = epsYoyPct,
        epsTrend = epsTrend,
        grossMarginDeltaPct = grossMarginDeltaPct,
        operatingMarginDeltaPct = operatingMarginDeltaPct,
        netMarginDeltaPct = netMarginDeltaPct,
        debtToEbitda = debtToEbitda,
        interestCoverage = interestCoverage,
        freeCashFlow = freeCashFlow,
        sectorPriceToSalesMedian = sectorPriceToSalesMedian,
        earningsDateUtc = earningsDateUtc,
        earningsSessions = earningsSessions,
        dataAgeDays = dataAgeDays,
        sector = sector
    )

    private fun candidateMatches(replay: ScanCandidate, original: CandidateEntity): Boolean =
        replay.ticker == original.ticker && replay.signal == original.signal &&
            close(replay.score, original.score) && close(replay.close, original.close) &&
            close(replay.sma20, original.sma20) && close(replay.sma50, original.sma50) &&
            close(replay.rsi14, original.rsi14) && close(replay.macd, original.macd, 0.0001) &&
            close(replay.macdSignal, original.macdSignal, 0.0001) &&
            close(replay.stochastic, original.stochastic) && close(replay.atr14, original.atr14) &&
            close(replay.relativeVolume, original.relativeVolume) && replay.setupType == original.setupType &&
            replay.quoteStatus == original.quoteStatus && replay.executionQuoteQuality == original.executionQuoteQuality &&
            replay.triggerConfirmed == original.triggerConfirmed &&
            closeNullable(replay.plannedTrigger, original.plannedTrigger) &&
            closeNullable(replay.maximumEntry, original.maximumEntry) &&
            replay.actionabilityAtExecution == original.actionabilityAtExecution

    private fun analysisMatches(replay: CandidateAnalysisEntity, original: CandidateAnalysisEntity): Boolean =
        close(replay.rsi6, original.rsi6) && close(replay.rsi14Canonical, original.rsi14Canonical) &&
            replay.rsi6GtRsi14 == original.rsi6GtRsi14 && close(replay.ema20, original.ema20) &&
            close(replay.ema50, original.ema50) && close(replay.ema200, original.ema200) &&
            close(replay.assetQualityScore, original.assetQualityScore) &&
            close(replay.setupQualityScore, original.setupQualityScore) &&
            close(replay.contextScore, original.contextScore) &&
            close(replay.institutionalScore, original.institutionalScore) &&
            close(replay.riskScore, original.riskScore) &&
            close(replay.finalTradeScore, original.finalTradeScore) &&
            replay.weeklyTrend == original.weeklyTrend && replay.stopAtrStatus == original.stopAtrStatus

    private fun planMatches(replay: CandidateTradePlanEntity, original: CandidateTradePlanEntity): Boolean =
        close(replay.priorResistance, original.priorResistance) &&
            closeNullable(replay.nextResistance, original.nextResistance) &&
            close(replay.swingLow, original.swingLow) && close(replay.structureScore, original.structureScore) &&
            close(replay.plannedEntry, original.plannedEntry) && close(replay.structuralStop, original.structuralStop) &&
            close(replay.structuralTarget, original.structuralTarget) && replay.stopType == original.stopType &&
            close(replay.stopAtrMultiple, original.stopAtrMultiple) && close(replay.structuralRr, original.structuralRr) &&
            replay.shares == original.shares && replay.riskPlanValid == original.riskPlanValid &&
            replay.legacyRank == original.legacyRank && replay.tradeRank == original.tradeRank &&
            replay.rankDelta == original.rankDelta && close(replay.auditedTradeScore, original.auditedTradeScore)

    private fun decisionMatches(replay: FinalDecisionEntity, original: FinalDecisionEntity): Boolean =
        replay.preliminarySignal == original.preliminarySignal && replay.finalSignal == original.finalSignal &&
            close(replay.finalTradeScore, original.finalTradeScore) &&
            replay.eligibleForContract == original.eligibleForContract && replay.confidence == original.confidence &&
            replay.macroRegime == original.macroRegime &&
            replay.fundamentalCoverage == original.fundamentalCoverage &&
            replay.institutionalCoverage == original.institutionalCoverage &&
            replay.executionFreshness == original.executionFreshness

    private fun close(first: Double, second: Double, tolerance: Double = 0.01): Boolean =
        abs(first - second) <= tolerance

    private fun closeNullable(first: Double?, second: Double?, tolerance: Double = 0.01): Boolean =
        if (first == null || second == null) first == second else close(first, second, tolerance)

    private fun ticker(value: String): String = value.trim().uppercase().replace(".", "-")
    private fun round2(value: Double) = round(value * 100.0) / 100.0
}
