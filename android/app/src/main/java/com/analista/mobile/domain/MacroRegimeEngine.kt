package com.analista.mobile.domain

import com.analista.mobile.data.MarketSnapshotEntity
import com.analista.mobile.data.PriceBar
import kotlin.math.round

object MacroRegimeEngine {
    const val VERSION = "macro-regime-1"

    data class Result(
        val macroScore: Double,
        val macroRegime: String,
        val riskAppetite: String,
        val ratesRegime: String,
        val liquidityRegime: String,
        val eventRisk: String,
        val sectorRegime: String,
        val confidence: String,
        val coveragePct: Double,
        val reasons: List<String>
    )

    fun assess(
        histories: Map<String, List<PriceBar>>,
        fallbackSnapshots: List<MarketSnapshotEntity> = emptyList()
    ): Result {
        val normalized = histories.mapKeys { it.key.trim().uppercase() }
        val reasons = mutableListOf<String>()
        val required = listOf("SPY", "QQQ", "IWM", "^VIX", "^TNX", "^TYX", "DX-Y.NYB", "CL=F", "BTC-USD")
        val validHistories = required.associateWith { normalized[it].orEmpty() }.filterValues { it.size >= 61 }
        val coveragePct = validHistories.size.toDouble() / required.size * 100.0

        fun returns(symbol: String, sessions: Int): Double? {
            val bars = validHistories[symbol] ?: return null
            val last = bars.last().close
            val prior = bars[bars.lastIndex - sessions].close
            return if (prior > 0.0) (last / prior - 1.0) * 100.0 else null
        }

        val snapshotByLabel = fallbackSnapshots.associateBy { it.label }
        fun oneDay(symbol: String, label: String): Double? =
            returns(symbol, 1) ?: snapshotByLabel[label]?.changePct
        fun latest(symbol: String, label: String): Double? =
            validHistories[symbol]?.lastOrNull()?.close ?: snapshotByLabel[label]?.close

        var score = 50.0
        val broadSymbols = listOf("SPY", "QQQ", "IWM")
        val broad20 = broadSymbols.mapNotNull { returns(it, 20) }
        val broad60 = broadSymbols.mapNotNull { returns(it, 60) }
        val broad1 = listOf(
            oneDay("SPY", "SPY"), oneDay("QQQ", "QQQ"), oneDay("IWM", "IWM")
        ).filterNotNull()
        broad1.forEach { score += directionalScore(it, 0.75, 3.0) }
        broad20.forEach { score += directionalScore(it, 3.0, 5.0) }
        broad60.forEach { score += directionalScore(it, 6.0, 6.0) }

        val riskAppetite = when {
            broad20.size < 2 || broad60.size < 2 -> "UNKNOWN"
            broad20.count { it > 0.0 } >= 2 && broad60.count { it > 0.0 } >= 2 -> "RISK_SEEKING"
            broad20.count { it < 0.0 } >= 2 && broad60.count { it < 0.0 } >= 2 -> "RISK_AVERSE"
            else -> "MIXED"
        }
        when (riskAppetite) {
            "RISK_SEEKING" -> reasons += "broad_market_positive_20d_60d"
            "RISK_AVERSE" -> reasons += "broad_market_negative_20d_60d"
            "UNKNOWN" -> reasons += "broad_market_history_incomplete"
        }

        val vix = latest("^VIX", "VIX")
        val vix20 = returns("^VIX", 20)
        if (vix != null) score += when {
            vix < 18.0 -> 8.0
            vix < 24.0 -> 2.0
            vix >= 30.0 -> -15.0
            else -> -7.0
        }
        if (vix20 != null && vix20 > 20.0) { score -= 5.0; reasons += "vix_rising_20d" }

        val tenYear = latest("^TNX", "US10Y")
        val thirtyYear = latest("^TYX", "US30Y")
        val ten20 = returns("^TNX", 20)
        val ten60 = returns("^TNX", 60)
        val curve = if (tenYear != null && thirtyYear != null) thirtyYear - tenYear else null
        val ratesRegime = when {
            ten20 == null || ten60 == null -> "UNKNOWN"
            ten20 > 3.0 && ten60 > 5.0 -> "RISING"
            ten20 < -3.0 && ten60 < -5.0 -> "FALLING"
            else -> "STABLE_MIXED"
        }
        if (ratesRegime == "RISING") { score -= 7.0; reasons += "rates_rising_20d_60d" }
        if (ratesRegime == "FALLING") { score += 3.0; reasons += "rates_falling_20d_60d" }
        if (curve != null && curve < 0.0) { score -= 3.0; reasons += "long_curve_inverted" }

        val dxy20 = returns("DX-Y.NYB", 20)
        val dxy60 = returns("DX-Y.NYB", 60)
        if (dxy20 != null && dxy20 > 2.0) { score -= 4.0; reasons += "dxy_strong_20d" }
        if (dxy60 != null && dxy60 > 4.0) score -= 3.0

        val oil20 = returns("CL=F", 20)
        val bitcoin20 = returns("BTC-USD", 20)
        if (oil20 != null && oil20 > 15.0) { score -= 2.0; reasons += "oil_inflation_impulse" }
        if (bitcoin20 != null && bitcoin20 > 10.0) score += 2.0
        if (bitcoin20 != null && bitcoin20 < -15.0) score -= 2.0

        val liquidityRegime = "UNKNOWN"
        val eventRisk = "UNKNOWN"
        val sectorRegime = "UNKNOWN"
        reasons += "liquidity_series_unavailable"
        reasons += "macro_event_calendar_unavailable"
        reasons += "sector_breadth_unavailable"

        val confidence = when {
            coveragePct >= 88.0 -> "HIGH"
            coveragePct >= 66.0 -> "PARTIAL"
            coveragePct > 0.0 || fallbackSnapshots.size >= 6 -> "LOW"
            else -> "UNKNOWN"
        }
        if (confidence != "HIGH") score -= when (confidence) {
            "PARTIAL" -> 2.0
            "LOW" -> 4.0
            else -> 6.0
        }
        score = score.coerceIn(0.0, 100.0)
        val regime = when {
            score >= 65.0 -> "RISK_ON"
            score <= 35.0 -> "RISK_OFF"
            else -> "MIXED"
        }
        return Result(
            macroScore = round2(score),
            macroRegime = regime,
            riskAppetite = riskAppetite,
            ratesRegime = ratesRegime,
            liquidityRegime = liquidityRegime,
            eventRisk = eventRisk,
            sectorRegime = sectorRegime,
            confidence = confidence,
            coveragePct = round2(coveragePct),
            reasons = reasons.distinct()
        )
    }

    private fun directionalScore(value: Double, threshold: Double, points: Double): Double = when {
        value >= threshold -> points
        value > 0.0 -> points / 2.0
        value <= -threshold -> -points
        else -> -points / 2.0
    }

    private fun round2(value: Double) = round(value * 100.0) / 100.0
}
