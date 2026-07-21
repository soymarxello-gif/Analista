package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import kotlin.math.abs
import kotlin.math.max

object SetupClassificationEngine {
    const val VERSION = "setup-classifier-2"

    data class Input(
        val bars: List<PriceBar>,
        val close: Double,
        val sma20: Double,
        val sma50: Double,
        val atr: Double,
        val rsi14: Double,
        val macd: Double,
        val macdSignal: Double,
        val relativeVolume: Double,
        val priorResistance: Double,
        val executionPrice: Double? = null
    )

    data class Assessment(
        val setupType: String,
        val setupValid: Boolean,
        val setupScore: Double,
        val triggerType: String,
        val invalidationType: String,
        val plannedTrigger: Double?,
        val reasons: List<String>
    )

    fun classify(input: Input): Assessment {
        require(input.bars.size >= 60)
        require(input.close > 0.0 && input.atr > 0.0)
        val latest = input.bars.last()
        val previous = input.bars[input.bars.lastIndex - 1]
        val trendUp = input.close > input.sma20 && input.sma20 > input.sma50
        val priorSessionBreakout = input.close > input.priorResistance && input.relativeVolume >= 1.2
        val execution = input.executionPrice
        val failedBreakout = priorSessionBreakout && execution != null && execution < input.priorResistance
        val breakoutTrigger = input.priorResistance + max(0.25 * input.atr, input.priorResistance * 0.005)
        val retestDistanceAtr = execution?.let { abs(it - input.priorResistance) / input.atr }
        val previousSma20 = input.bars.dropLast(1).takeLast(20).map { it.close }.average()
        val supportReclaim = previous.close <= previousSma20 && input.close > input.sma20 && input.relativeVolume >= 1.0
        val distanceEma20Atr = abs(input.close - input.sma20) / input.atr
        val distanceEma50Atr = abs(input.close - input.sma50) / input.atr
        val constructiveMomentum = input.rsi14 in 45.0..70.0 && input.macd >= input.macdSignal - 0.15 * input.atr
        val recentRanges = input.bars.takeLast(10).map { it.high - it.low }
        val priorRanges = input.bars.takeLast(30).dropLast(10).map { it.high - it.low }
        val compressionRatio = recentRanges.average() / priorRanges.average().coerceAtLeast(0.0001)
        val volatilityContraction = trendUp && compressionRatio <= 0.70 && input.relativeVolume <= 1.2
        val pullbackTrigger = latest.high + max(0.10 * input.atr, latest.high * 0.002)
        val vcpResistance = input.bars.takeLast(11).dropLast(1).maxOf { it.high }
        val vcpTrigger = vcpResistance + max(0.15 * input.atr, vcpResistance * 0.003)

        return when {
            failedBreakout -> assessment(
                type = "FAILED_BREAKOUT", valid = false, score = 10.0,
                triggerType = "NONE", invalidationType = "LOST_PRIOR_RESISTANCE", trigger = null,
                reasons = listOf("prior_breakout_lost", "execution_below_resistance")
            )
            priorSessionBreakout && execution != null && retestDistanceAtr != null &&
                retestDistanceAtr <= 0.35 && execution < breakoutTrigger -> assessment(
                type = "BREAKOUT_RETEST", valid = true,
                score = score(72.0, trendUp, constructiveMomentum, input.relativeVolume >= 0.8),
                triggerType = "RETEST_RECLAIM", invalidationType = "RETEST_LOW",
                trigger = input.priorResistance + 0.10 * input.atr,
                reasons = listOf("prior_breakout", "controlled_retest")
            )
            priorSessionBreakout -> assessment(
                type = "BREAKOUT", valid = true,
                score = score(75.0, trendUp, input.relativeVolume >= 1.5, input.rsi14 in 50.0..70.0),
                triggerType = "RESISTANCE_BUFFER", invalidationType = "CLOSE_BELOW_BREAKOUT_LEVEL",
                trigger = breakoutTrigger,
                reasons = listOf("prior_session_breakout", "daily_structure_valid")
            )
            supportReclaim -> assessment(
                type = "SUPPORT_RECLAIM", valid = true,
                score = score(68.0, input.sma20 > input.sma50, constructiveMomentum, input.relativeVolume >= 1.2),
                triggerType = "RECLAIM_BAR_HIGH", invalidationType = "RECLAIM_BAR_LOW",
                trigger = pullbackTrigger,
                reasons = listOf("sma20_reclaimed", "reclaim_volume_confirmed")
            )
            trendUp && distanceEma20Atr <= 0.50 && constructiveMomentum -> assessment(
                type = "PULLBACK_EMA20", valid = true,
                score = score(70.0, input.relativeVolume <= 1.2, input.rsi14 >= 50.0, latest.close > latest.low),
                triggerType = "PULLBACK_BAR_HIGH", invalidationType = "EMA20_OR_SWING_LOW",
                trigger = pullbackTrigger,
                reasons = listOf("trend_up", "price_near_ema20", "momentum_constructive")
            )
            input.sma20 > input.sma50 && distanceEma50Atr <= 0.50 && constructiveMomentum -> assessment(
                type = "PULLBACK_EMA50", valid = true,
                score = score(65.0, input.close >= input.sma50, input.relativeVolume <= 1.2, input.rsi14 >= 45.0),
                triggerType = "PULLBACK_BAR_HIGH", invalidationType = "EMA50_OR_SWING_LOW",
                trigger = pullbackTrigger,
                reasons = listOf("intermediate_trend_up", "price_near_ema50", "momentum_constructive")
            )
            volatilityContraction -> assessment(
                type = "VOLATILITY_CONTRACTION", valid = true,
                score = score(72.0, compressionRatio <= 0.60, input.rsi14 in 50.0..70.0, input.macd >= input.macdSignal),
                triggerType = "CONTRACTION_RESISTANCE", invalidationType = "CONTRACTION_BASE_LOW",
                trigger = vcpTrigger,
                reasons = listOf("trend_up", "range_contraction", "volume_not_expanding")
            )
            else -> assessment(
                type = "NO_VALID_SETUP", valid = false, score = 0.0,
                triggerType = "NONE", invalidationType = "NONE", trigger = null,
                reasons = listOf("no_supported_swing_structure")
            )
        }
    }

    private fun score(base: Double, vararg confirmations: Boolean): Double =
        (base + confirmations.count { it } * 7.0).coerceIn(0.0, 100.0)

    private fun assessment(
        type: String,
        valid: Boolean,
        score: Double,
        triggerType: String,
        invalidationType: String,
        trigger: Double?,
        reasons: List<String>
    ) = Assessment(type, valid, score, triggerType, invalidationType, trigger, reasons)
}
