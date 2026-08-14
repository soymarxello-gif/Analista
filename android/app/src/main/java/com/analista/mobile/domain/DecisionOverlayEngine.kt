package com.analista.mobile.domain

import com.analista.mobile.data.CandidateEnrichmentEntity
import com.analista.mobile.data.CanonicalAnalysis
import com.analista.mobile.data.FundamentalMetrics
import com.analista.mobile.data.FundamentalSnapshotRegistry
import com.analista.mobile.data.InsiderTransactionRegistry
import com.analista.mobile.data.MarketHistoryRegistry
import com.analista.mobile.data.MarketSnapshotEntity
import com.analista.mobile.data.OfficialContextRegistry
import com.analista.mobile.data.OptionChainRegistry
import com.analista.mobile.data.OptionChainSnapshot
import com.analista.mobile.data.PriceBar
import com.analista.mobile.data.ScanCandidate
import kotlin.math.round

object DecisionOverlayEngine {
    const val ENGINE_VERSION = "android-v3-overlays-8-advisory"

    data class OverlayResult(
        val contextScore: Double,
        val fundamentalScore: Double,
        val institutionalScore: Double,
        val finalTradeScore: Double,
        val macroRegime: String,
        val optionsBias: String,
        val fundamentalCoverage: String,
        val optionsCoverage: String,
        val confidencePenalty: Double,
        val breakdown: String,
        val riskAppetite: String = "UNKNOWN",
        val ratesRegime: String = "UNKNOWN",
        val liquidityRegime: String = "UNKNOWN",
        val eventRisk: String = "UNKNOWN",
        val sectorRegime: String = "UNKNOWN",
        val macroConfidence: String = "UNKNOWN",
        val macroCoveragePct: Double = 0.0,
        val earningsRiskStatus: String = "UNKNOWN",
        val fundamentalReasons: List<String> = emptyList(),
        val institutionalConflict: String = "NONE",
        val institutionalReasons: List<String> = emptyList()
    )

    data class ResolvedInputs(
        val macroHistories: Map<String, List<PriceBar>>,
        val fundamentalMetrics: FundamentalMetrics?,
        val fundamentalAvailable: Boolean,
        val fundamentalCapturedAtUtc: Long?,
        val optionChain: OptionChainSnapshot?,
        val legacyEnrichment: CandidateEnrichmentEntity?,
        val officialContext: OfficialContextEngine.Assessment? = null,
        val insiderSnapshot: InsiderTransactionRegistry.Snapshot? = null
    )

    fun apply(
        candidate: ScanCandidate,
        base: CanonicalAnalysis,
        macro: List<MarketSnapshotEntity>,
        enrichment: CandidateEnrichmentEntity?
    ): OverlayResult {
        val registeredFundamental = FundamentalSnapshotRegistry.get(candidate.ticker)
        val fundamentalMetrics = registeredFundamental?.metrics ?: enrichment
            ?.takeIf { it.fundamentalsStatus in setOf("AVAILABLE_COMPLETE", "AVAILABLE_PARTIAL") }
            ?.let(::legacyFundamentalMetrics)
        val assessedOfficial = OfficialContextEngine.assess(
            fred = OfficialContextRegistry.fredSnapshot(),
            cboe = OfficialContextRegistry.cboe(),
            cftc = OfficialContextRegistry.cftc()
        )
        val effectiveOfficial = assessedOfficial.takeIf {
            it.macro.coveragePct > 0.0 ||
                it.institutional.futuresScore != null ||
                it.institutional.marketOptionsRegime != "UNKNOWN"
        }
        return applyResolved(
            candidate = candidate,
            base = base,
            macro = macro,
            inputs = ResolvedInputs(
                macroHistories = MarketHistoryRegistry.snapshot(macro.map { it.symbol }),
                fundamentalMetrics = fundamentalMetrics,
                fundamentalAvailable = registeredFundamental != null ||
                    (enrichment?.fundamentalsStatus in setOf("AVAILABLE_COMPLETE", "AVAILABLE_PARTIAL")),
                fundamentalCapturedAtUtc = registeredFundamental?.capturedAtUtc ?: enrichment?.capturedAtUtc,
                optionChain = OptionChainRegistry.get(candidate.ticker),
                legacyEnrichment = enrichment,
                officialContext = effectiveOfficial,
                insiderSnapshot = InsiderTransactionRegistry.get(candidate.ticker)
            )
        )
    }

    fun applyResolved(
        candidate: ScanCandidate,
        base: CanonicalAnalysis,
        macro: List<MarketSnapshotEntity>,
        inputs: ResolvedInputs
    ): OverlayResult {
        val context = MacroRegimeEngine.assess(inputs.macroHistories, macro, inputs.officialContext?.macro)
        val fundamental = resolvedFundamental(inputs)
        val institutional = institutionalAssessment(
            candidate,
            inputs.optionChain,
            inputs.legacyEnrichment,
            inputs.officialContext?.institutional,
            inputs.insiderSnapshot
        )

        val confidencePenalty = 0.0
        val final = base.finalTradeScore

        val breakdown = listOf(
            base.scoreBreakdown,
            "fundamental=${round2(fundamental.score)}:${fundamental.status}:${fundamental.earningsRiskStatus}",
            "fundamental_reasons=${fundamental.reasons.joinToString("|")}",
            "macro=${round2(context.macroScore)}:${context.macroRegime}:${context.confidence}:20d_60d_official",
            "risk_appetite=${context.riskAppetite}",
            "rates=${context.ratesRegime}",
            "liquidity=${context.liquidityRegime}",
            "event_risk=${context.eventRisk}",
            "sector=${context.sectorRegime}",
            "institutional=${round2(institutional.score)}:${institutional.bias}:${institutional.coverage}:${institutional.conflict}",
            "institutional_reasons=${institutional.reasons.joinToString("|")}",
            "officialContextVersion=${inputs.officialContext?.engineVersion ?: "UNAVAILABLE"}",
            "insiderEngineVersion=${InsiderAssessmentEngine.VERSION}",
            "selection_score_unchanged=${round2(final)}",
            "context_role=ADVISORY_ONLY_NEVER_FILTERS_OR_PENALIZES"
        ).joinToString(";")

        return OverlayResult(
            contextScore = round2(context.macroScore),
            fundamentalScore = round2(fundamental.score),
            institutionalScore = round2(institutional.score),
            finalTradeScore = round2(final),
            macroRegime = context.macroRegime,
            optionsBias = institutional.bias,
            fundamentalCoverage = fundamental.status,
            optionsCoverage = institutional.coverage,
            confidencePenalty = round2(confidencePenalty),
            breakdown = breakdown,
            riskAppetite = context.riskAppetite,
            ratesRegime = context.ratesRegime,
            liquidityRegime = context.liquidityRegime,
            eventRisk = context.eventRisk,
            sectorRegime = context.sectorRegime,
            macroConfidence = context.confidence,
            macroCoveragePct = context.coveragePct,
            earningsRiskStatus = fundamental.earningsRiskStatus,
            fundamentalReasons = fundamental.reasons,
            institutionalConflict = institutional.conflict,
            institutionalReasons = institutional.reasons
        )
    }

    private fun resolvedFundamental(inputs: ResolvedInputs): FundamentalAssessmentEngine.Result {
        if (!inputs.fundamentalAvailable || inputs.fundamentalMetrics == null) {
            return FundamentalAssessmentEngine.Result(50.0, 0.0, "EMPTY", "UNKNOWN", listOf("fundamentals_unavailable"))
        }
        return FundamentalAssessmentEngine.assess(
            inputs.fundamentalMetrics,
            inputs.fundamentalCapturedAtUtc?.takeIf { it > 0L } ?: System.currentTimeMillis()
        )
    }

    private data class InstitutionalResult(
        val score: Double,
        val bias: String,
        val coverage: String,
        val conflict: String,
        val reasons: List<String>
    )

    private data class LegacyOptionInput(
        val component: InstitutionalContrarianEngine.Component?,
        val bias: String?
    )

    private fun institutionalAssessment(
        candidate: ScanCandidate,
        chain: OptionChainSnapshot?,
        enrichment: CandidateEnrichmentEntity?,
        official: OfficialContextEngine.InstitutionalAssessment?,
        insiderSnapshot: InsiderTransactionRegistry.Snapshot?
    ): InstitutionalResult {
        val optionAssessment = chain?.let(OptionMetricsEngine::assess)
        val legacyOption = if (optionAssessment == null) legacyOptionsInput(enrichment) else LegacyOptionInput(null, null)
        val insiderAssessment = InsiderAssessmentEngine.assess(insiderSnapshot)
        val volumeScore = when {
            candidate.close > candidate.sma20 && candidate.relativeVolume >= 1.5 -> 70.0
            candidate.close > candidate.sma20 && candidate.relativeVolume >= 1.2 -> 60.0
            candidate.relativeVolume < 0.75 -> 40.0
            else -> 50.0
        }
        val futuresComponent = InstitutionalContrarianEngine.Component(
            score = official?.futuresScore,
            status = official?.futuresStatus ?: "UNKNOWN",
            reasons = official?.reasons.orEmpty().filter { it.startsWith("cftc_") }
        )
        val institutional = InstitutionalContrarianEngine.assess(
            InstitutionalContrarianEngine.Input(
                options = optionAssessment,
                optionsComponent = legacyOption.component,
                optionsBiasOverride = legacyOption.bias,
                volumeAccumulation = InstitutionalContrarianEngine.Component(
                    volumeScore,
                    "AVAILABLE",
                    listOf("price_volume_accumulation_proxy")
                ),
                insiders = InstitutionalContrarianEngine.Component(
                    score = insiderAssessment.score,
                    status = insiderAssessment.coverageStatus,
                    reasons = insiderAssessment.reasons
                ),
                futuresPositioning = futuresComponent,
                marketOptionsRegime = official?.marketOptionsRegime ?: "UNKNOWN",
                marketOptionsAdjustment = official?.marketOptionsAdjustment ?: 0.0,
                priceTrendConstructive = candidate.close > candidate.sma20,
                technicalScore = candidate.score.coerceIn(0.0, 100.0)
            )
        )
        return InstitutionalResult(
            score = institutional.adjustedInstitutionalScore,
            bias = institutional.optionsBias,
            coverage = institutional.coverageStatus,
            conflict = institutional.conflict,
            reasons = (institutional.reasons + official?.reasons.orEmpty()).distinct()
        )
    }

    private fun legacyOptionsInput(e: CandidateEnrichmentEntity?): LegacyOptionInput {
        if (e == null || e.optionsStatus == "UNAVAILABLE") return LegacyOptionInput(null, "UNKNOWN_OPTIONS_FLOW")
        val ratio = e.optionsPutCallOi ?: return LegacyOptionInput(
            InstitutionalContrarianEngine.Component(null, "PARTIAL", listOf("options_ratio_missing")),
            "UNKNOWN_OPTIONS_FLOW"
        )
        val bias = when {
            ratio < 0.35 -> "CROWDED_BULLISH"
            ratio < 0.70 -> "BULLISH_WITH_DATA"
            ratio > 1.80 -> "CROWDED_BEARISH"
            ratio > 1.15 -> "BEARISH_WITH_DATA"
            else -> "NEUTRAL_WITH_DATA"
        }
        val score = when (bias) {
            "BULLISH_WITH_DATA" -> 65.0
            "BEARISH_WITH_DATA" -> 38.0
            "CROWDED_BULLISH" -> 42.0
            "CROWDED_BEARISH" -> 58.0
            else -> 50.0
        }
        val complete = e.optionsNearCallOi != null && e.optionsNearPutOi != null && e.optionsExpiry != null
        return LegacyOptionInput(
            InstitutionalContrarianEngine.Component(
                score,
                if (complete) "COMPLETE" else "PARTIAL",
                listOf("legacy_options_fallback")
            ),
            bias
        )
    }

    private fun legacyFundamentalMetrics(enrichment: CandidateEnrichmentEntity) = FundamentalMetrics(
        marketCap = enrichment.marketCap,
        trailingPe = enrichment.trailingPe,
        priceToSales = enrichment.priceToSales,
        epsTrailing = enrichment.epsTrailing,
        revenueGrowthPct = enrichment.revenueGrowthPct,
        grossMarginPct = enrichment.grossMarginPct,
        operatingMarginPct = enrichment.operatingMarginPct,
        profitMarginPct = enrichment.profitMarginPct,
        debtToEquity = enrichment.debtToEquity
    )

    private fun round2(value: Double) = round(value * 100.0) / 100.0
}
