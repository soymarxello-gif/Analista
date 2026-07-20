package com.analista.mobile.domain

import com.analista.mobile.data.CandidateEnrichmentEntity
import com.analista.mobile.data.CanonicalAnalysis
import com.analista.mobile.data.MarketHistoryRegistry
import com.analista.mobile.data.MarketSnapshotEntity
import com.analista.mobile.data.ScanCandidate
import kotlin.math.round

object DecisionOverlayEngine {
    const val ENGINE_VERSION = "android-v3-overlays-2"

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
        val macroCoveragePct: Double = 0.0
    )

    fun apply(
        candidate: ScanCandidate,
        base: CanonicalAnalysis,
        macro: List<MarketSnapshotEntity>,
        enrichment: CandidateEnrichmentEntity?
    ): OverlayResult {
        val histories = MarketHistoryRegistry.snapshot(macro.map { it.symbol })
        val context = MacroRegimeEngine.assess(histories, macro)
        val fundamental = fundamentalScore(enrichment)
        val institutional = optionsScore(enrichment)

        var confidencePenalty = 0.0
        if (fundamental.coverage != "COMPLETE") confidencePenalty += if (fundamental.coverage == "PARTIAL") 2.0 else 4.0
        if (institutional.coverage != "COMPLETE") confidencePenalty += if (institutional.coverage == "PARTIAL") 2.0 else 4.0
        confidencePenalty += when (context.confidence) {
            "HIGH" -> 0.0
            "PARTIAL" -> 2.0
            "LOW" -> 4.0
            else -> 6.0
        }

        var final = base.finalTradeScore +
            0.10 * (context.macroScore - 50.0) +
            0.10 * (fundamental.score - 50.0) +
            0.10 * (institutional.score - 50.0) -
            confidencePenalty

        if (context.macroRegime == "RISK_OFF") final -= 5.0
        if (context.ratesRegime == "RISING") final -= 2.0
        if (institutional.bias == "CROWDED_BULLISH") final -= 8.0
        if (candidate.signal == "VETO" || candidate.setupType == "NO_VALID_SETUP") final = minOf(final, 49.0)
        if (candidate.executionQuoteQuality == "LOW") final = minOf(final, 59.0)
        final = final.coerceIn(0.0, 100.0)

        val breakdown = listOf(
            base.scoreBreakdown,
            "fundamental=${round2(fundamental.score)}:${fundamental.coverage}",
            "macro=${round2(context.macroScore)}:${context.macroRegime}:${context.confidence}:20d_60d",
            "risk_appetite=${context.riskAppetite}",
            "rates=${context.ratesRegime}",
            "liquidity=${context.liquidityRegime}",
            "event_risk=${context.eventRisk}",
            "sector=${context.sectorRegime}",
            "institutional=${round2(institutional.score)}:${institutional.bias}:${institutional.coverage}",
            "confidence_penalty=${round2(confidencePenalty)}"
        ).joinToString(";")

        return OverlayResult(
            contextScore = round2(context.macroScore),
            fundamentalScore = round2(fundamental.score),
            institutionalScore = round2(institutional.score),
            finalTradeScore = round2(final),
            macroRegime = context.macroRegime,
            optionsBias = institutional.bias,
            fundamentalCoverage = fundamental.coverage,
            optionsCoverage = institutional.coverage,
            confidencePenalty = round2(confidencePenalty),
            breakdown = breakdown,
            riskAppetite = context.riskAppetite,
            ratesRegime = context.ratesRegime,
            liquidityRegime = context.liquidityRegime,
            eventRisk = context.eventRisk,
            sectorRegime = context.sectorRegime,
            macroConfidence = context.confidence,
            macroCoveragePct = context.coveragePct
        )
    }

    private data class FundamentalResult(val score: Double, val coverage: String)

    private fun fundamentalScore(e: CandidateEnrichmentEntity?): FundamentalResult {
        if (e == null || e.fundamentalsStatus == "UNAVAILABLE") return FundamentalResult(50.0, "UNKNOWN")
        val values = listOf(e.revenueGrowthPct, e.grossMarginPct, e.operatingMarginPct, e.profitMarginPct, e.debtToEquity, e.priceToSales)
        val available = values.count { it != null }
        if (available == 0) return FundamentalResult(50.0, "UNKNOWN")
        var score = 50.0
        e.revenueGrowthPct?.let { score += when { it >= 20 -> 12.0; it >= 8 -> 7.0; it < 0 -> -12.0; else -> 1.0 } }
        e.operatingMarginPct?.let { score += when { it >= 20 -> 10.0; it >= 10 -> 5.0; it < 0 -> -12.0; else -> 0.0 } }
        e.profitMarginPct?.let { score += when { it >= 15 -> 8.0; it >= 5 -> 4.0; it < 0 -> -10.0; else -> 0.0 } }
        e.debtToEquity?.let { score += when { it <= 50 -> 6.0; it <= 150 -> 1.0; it > 300 -> -10.0; else -> -4.0 } }
        e.priceToSales?.let { score += when { it <= 3 -> 5.0; it >= 15 -> -6.0; else -> 0.0 } }
        val coverage = if (available >= 5) "COMPLETE" else "PARTIAL"
        return FundamentalResult(score.coerceIn(0.0, 100.0), coverage)
    }

    private data class InstitutionalResult(val score: Double, val bias: String, val coverage: String)

    private fun optionsScore(e: CandidateEnrichmentEntity?): InstitutionalResult {
        if (e == null || e.optionsStatus == "UNAVAILABLE") return InstitutionalResult(50.0, "UNKNOWN_OPTIONS_FLOW", "UNKNOWN")
        val ratio = e.optionsPutCallOi ?: return InstitutionalResult(50.0, "UNKNOWN_OPTIONS_FLOW", "PARTIAL")
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
        return InstitutionalResult(score, bias, if (complete) "COMPLETE" else "PARTIAL")
    }

    private fun round2(value: Double) = round(value * 100.0) / 100.0
}
