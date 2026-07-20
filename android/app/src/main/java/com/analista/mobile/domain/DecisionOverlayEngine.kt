package com.analista.mobile.domain

import com.analista.mobile.data.CandidateEnrichmentEntity
import com.analista.mobile.data.CanonicalAnalysis
import com.analista.mobile.data.FundamentalMetrics
import com.analista.mobile.data.FundamentalSnapshotRegistry
import com.analista.mobile.data.MarketHistoryRegistry
import com.analista.mobile.data.MarketSnapshotEntity
import com.analista.mobile.data.OptionChainRegistry
import com.analista.mobile.data.ScanCandidate
import kotlin.math.round

object DecisionOverlayEngine {
    const val ENGINE_VERSION = "android-v3-overlays-4"

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

    fun apply(
        candidate: ScanCandidate,
        base: CanonicalAnalysis,
        macro: List<MarketSnapshotEntity>,
        enrichment: CandidateEnrichmentEntity?
    ): OverlayResult {
        val histories = MarketHistoryRegistry.snapshot(macro.map { it.symbol })
        val context = MacroRegimeEngine.assess(histories, macro)
        val fundamental = temporalFundamental(candidate.ticker, enrichment)
        val institutional = institutionalAssessment(candidate, enrichment)

        var confidencePenalty = 0.0
        confidencePenalty += when (fundamental.status) {
            "COMPLETE" -> 0.0
            "PARTIAL" -> 2.0
            "STALE" -> 5.0
            else -> 4.0
        }
        if (institutional.coverage != "COMPLETE") {
            confidencePenalty += if (institutional.coverage == "PARTIAL") 2.0 else 4.0
        }
        confidencePenalty += when (context.confidence) {
            "HIGH" -> 0.0
            "PARTIAL" -> 2.0
            "LOW" -> 4.0
            else -> 6.0
        }

        var final = base.finalTradeScore +
            0.10 * (context.macroScore - 50.0) +
            0.15 * (fundamental.score - 50.0) +
            0.15 * (institutional.score - 50.0) -
            confidencePenalty

        if (context.macroRegime == "RISK_OFF") final -= 5.0
        if (context.ratesRegime == "RISING") final -= 2.0
        if (fundamental.earningsRiskStatus == "IMMINENT") final -= 5.0
        if (fundamental.status == "STALE") final -= 3.0
        if (institutional.bias == "CROWDED_BULLISH") final -= 8.0
        if (institutional.conflict == "HIGH") final = minOf(final, 59.0)
        if (candidate.signal == "VETO" || candidate.setupType == "NO_VALID_SETUP") final = minOf(final, 49.0)
        if (candidate.executionQuoteQuality == "LOW") final = minOf(final, 59.0)
        final = final.coerceIn(0.0, 100.0)

        val breakdown = listOf(
            base.scoreBreakdown,
            "fundamental=${round2(fundamental.score)}:${fundamental.status}:${fundamental.earningsRiskStatus}",
            "fundamental_reasons=${fundamental.reasons.joinToString("|")}",
            "macro=${round2(context.macroScore)}:${context.macroRegime}:${context.confidence}:20d_60d",
            "risk_appetite=${context.riskAppetite}",
            "rates=${context.ratesRegime}",
            "liquidity=${context.liquidityRegime}",
            "event_risk=${context.eventRisk}",
            "sector=${context.sectorRegime}",
            "institutional=${round2(institutional.score)}:${institutional.bias}:${institutional.coverage}:${institutional.conflict}",
            "institutional_reasons=${institutional.reasons.joinToString("|")}",
            "confidence_penalty=${round2(confidencePenalty)}"
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

    private fun temporalFundamental(
        ticker: String,
        enrichment: CandidateEnrichmentEntity?
    ): FundamentalAssessmentEngine.Result {
        if (enrichment == null || enrichment.fundamentalsStatus !in setOf("AVAILABLE_COMPLETE", "AVAILABLE_PARTIAL")) {
            return FundamentalAssessmentEngine.Result(50.0, 0.0, "EMPTY", "UNKNOWN", listOf("fundamentals_unavailable"))
        }
        val metrics = FundamentalSnapshotRegistry.get(ticker)?.metrics ?: FundamentalMetrics(
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
        return FundamentalAssessmentEngine.assess(metrics, enrichment.capturedAtUtc)
    }

    private data class InstitutionalResult(
        val score: Double,
        val bias: String,
        val coverage: String,
        val conflict: String,
        val reasons: List<String>
    )

    private fun institutionalAssessment(
        candidate: ScanCandidate,
        enrichment: CandidateEnrichmentEntity?
    ): InstitutionalResult {
        val chain = OptionChainRegistry.get(candidate.ticker)
        if (chain != null) {
            val optionAssessment = OptionMetricsEngine.assess(chain)
            val volumeScore = when {
                candidate.close > candidate.sma20 && candidate.relativeVolume >= 1.5 -> 70.0
                candidate.close > candidate.sma20 && candidate.relativeVolume >= 1.2 -> 60.0
                candidate.relativeVolume < 0.75 -> 40.0
                else -> 50.0
            }
            val institutional = InstitutionalContrarianEngine.assess(
                InstitutionalContrarianEngine.Input(
                    options = optionAssessment,
                    volumeAccumulation = InstitutionalContrarianEngine.Component(
                        volumeScore,
                        "AVAILABLE",
                        listOf("price_volume_accumulation_proxy")
                    ),
                    insiders = InstitutionalContrarianEngine.Component(null, "UNKNOWN"),
                    futuresPositioning = InstitutionalContrarianEngine.Component(null, "UNKNOWN"),
                    priceTrendConstructive = candidate.close > candidate.sma20,
                    technicalScore = candidate.score.coerceIn(0.0, 100.0)
                )
            )
            return InstitutionalResult(
                score = institutional.adjustedInstitutionalScore,
                bias = institutional.optionsBias,
                coverage = institutional.coverageStatus,
                conflict = institutional.conflict,
                reasons = institutional.reasons
            )
        }
        return legacyOptionsScore(enrichment)
    }

    private fun legacyOptionsScore(e: CandidateEnrichmentEntity?): InstitutionalResult {
        if (e == null || e.optionsStatus == "UNAVAILABLE") {
            return InstitutionalResult(50.0, "UNKNOWN_OPTIONS_FLOW", "UNKNOWN", "NONE", listOf("options_unavailable"))
        }
        val ratio = e.optionsPutCallOi ?: return InstitutionalResult(
            50.0,
            "UNKNOWN_OPTIONS_FLOW",
            "PARTIAL",
            "NONE",
            listOf("options_ratio_missing")
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
        val conflict = if (bias == "BEARISH_WITH_DATA" && score <= 40.0 && complete) "HIGH" else "NONE"
        return InstitutionalResult(score, bias, if (complete) "COMPLETE" else "PARTIAL", conflict, listOf("legacy_options_fallback"))
    }

    private fun round2(value: Double) = round(value * 100.0) / 100.0
}
