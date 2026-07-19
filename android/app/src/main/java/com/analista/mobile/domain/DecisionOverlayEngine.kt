package com.analista.mobile.domain

import com.analista.mobile.data.CandidateEnrichmentEntity
import com.analista.mobile.data.CanonicalAnalysis
import com.analista.mobile.data.MarketSnapshotEntity
import com.analista.mobile.data.ScanCandidate
import kotlin.math.round

object DecisionOverlayEngine {
    const val ENGINE_VERSION = "android-v2-overlays-1"

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
        val breakdown: String
    )

    fun apply(
        candidate: ScanCandidate,
        base: CanonicalAnalysis,
        macro: List<MarketSnapshotEntity>,
        enrichment: CandidateEnrichmentEntity?
    ): OverlayResult {
        val context = macroScore(macro)
        val fundamental = fundamentalScore(enrichment)
        val institutional = optionsScore(enrichment)

        var confidencePenalty = 0.0
        if (fundamental.coverage != "COMPLETE") confidencePenalty += if (fundamental.coverage == "PARTIAL") 2.0 else 4.0
        if (institutional.coverage != "COMPLETE") confidencePenalty += if (institutional.coverage == "PARTIAL") 2.0 else 4.0
        if (macro.size < 6) confidencePenalty += 3.0

        var final = base.finalTradeScore +
            0.10 * (context.score - 50.0) +
            0.10 * (fundamental.score - 50.0) +
            0.10 * (institutional.score - 50.0) -
            confidencePenalty

        if (institutional.bias == "CROWDED_BULLISH") final -= 8.0
        if (candidate.signal == "VETO" || candidate.setupType == "NO_VALID_SETUP") final = minOf(final, 49.0)
        if (candidate.executionQuoteQuality == "LOW") final = minOf(final, 59.0)
        final = final.coerceIn(0.0, 100.0)

        val breakdown = listOf(
            base.scoreBreakdown,
            "fundamental=${round2(fundamental.score)}:${fundamental.coverage}",
            "macro=${round2(context.score)}:${context.regime}",
            "institutional=${round2(institutional.score)}:${institutional.bias}:${institutional.coverage}",
            "confidence_penalty=${round2(confidencePenalty)}"
        ).joinToString(";")

        return OverlayResult(
            contextScore = round2(context.score),
            fundamentalScore = round2(fundamental.score),
            institutionalScore = round2(institutional.score),
            finalTradeScore = round2(final),
            macroRegime = context.regime,
            optionsBias = institutional.bias,
            fundamentalCoverage = fundamental.coverage,
            optionsCoverage = institutional.coverage,
            confidencePenalty = round2(confidencePenalty),
            breakdown = breakdown
        )
    }

    private data class MacroResult(val score: Double, val regime: String)

    private fun macroScore(items: List<MarketSnapshotEntity>): MacroResult {
        val byLabel = items.associateBy { it.label }
        val spy = byLabel["SPY"]?.changePct
        val qqq = byLabel["QQQ"]?.changePct
        val iwm = byLabel["IWM"]?.changePct
        val vix = byLabel["VIX"]?.close
        val us10yChange = byLabel["US10Y"]?.changePct
        val dxyChange = byLabel["DXY"]?.changePct

        var score = 50.0
        listOfNotNull(spy, qqq, iwm).forEach { score += when { it >= 0.75 -> 6.0; it > 0.0 -> 3.0; it <= -0.75 -> -6.0; else -> -3.0 } }
        if (vix != null) score += when { vix < 18.0 -> 8.0; vix < 24.0 -> 2.0; vix >= 30.0 -> -15.0; else -> -7.0 }
        if (us10yChange != null && us10yChange > 1.5) score -= 5.0
        if (dxyChange != null && dxyChange > 0.5) score -= 4.0
        score = score.coerceIn(0.0, 100.0)
        val regime = when { score >= 65.0 -> "RISK_ON"; score <= 35.0 -> "RISK_OFF"; else -> "MIXED" }
        return MacroResult(score, regime)
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
