package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min

object StructureRiskEngine {
    const val VERSION = "structure-risk-2"

    data class StructureAssessment(
        val priorResistance: Double,
        val nextResistance: Double?,
        val support: Double?,
        val swingLow: Double,
        val closeLocationValue: Double,
        val baseRangeAtr: Double,
        val volatilityCompression: Double,
        val resistanceTouches: Int,
        val structureScore: Double,
        val reasons: List<String>
    )

    data class StopCandidate(
        val type: String,
        val price: Double,
        val distanceAtr: Double,
        val distancePct: Double,
        val structuralReason: String,
        val valid: Boolean,
        val setupPriority: Int
    )

    data class RiskPlan(
        val entry: Double,
        val stop: Double,
        val target: Double,
        val stopType: String,
        val stopAtrMultiple: Double,
        val rr: Double,
        val riskPct: Double,
        val rewardPct: Double,
        val shares: Int,
        val positionValue: Double,
        val riskBudget: Double,
        val valid: Boolean,
        val reasons: List<String>,
        val stopCandidates: List<StopCandidate> = emptyList()
    )

    fun assess(bars: List<PriceBar>, atr: Double): StructureAssessment {
        require(bars.size >= 60)
        require(atr > 0.0)
        val latest = bars.last()
        val prior = bars.dropLast(1)
        val structureWindow = prior.takeLast(120)
        val priorResistance = structureWindow.takeLast(60).maxOf { it.high }
        val tolerance = max(0.25 * atr, latest.close * 0.005)
        val resistanceClusters = relevantLevels(
            values = structureWindow.map { it.high }.filter { it > latest.close },
            tolerance = tolerance,
            minimumTouches = 2
        )
        val supportClusters = relevantLevels(
            values = structureWindow.map { it.low }.filter { it < latest.close },
            tolerance = tolerance,
            minimumTouches = 2
        )
        val nextResistance = resistanceClusters.minOrNull()
        val support = supportClusters.maxOrNull()
        val swingLow = prior.takeLast(20).minOf { it.low }
        val range = max(0.000001, latest.high - latest.low)
        val clv = ((latest.close - latest.low) / range).coerceIn(0.0, 1.0)
        val base = prior.takeLast(20)
        val baseRangeAtr = (base.maxOf { it.high } - base.minOf { it.low }) / atr
        val recentAtrProxy = prior.takeLast(10).map { it.high - it.low }.average()
        val priorAtrProxy = prior.takeLast(30).dropLast(10).map { it.high - it.low }.average().takeIf { it > 0 }
            ?: recentAtrProxy
        val compression = (recentAtrProxy / priorAtrProxy).coerceAtLeast(0.0)
        val touchTolerance = max(0.25 * atr, priorResistance * 0.005)
        val touches = structureWindow.takeLast(60).count { abs(it.high - priorResistance) <= touchTolerance }
        var score = 0.0
        val reasons = mutableListOf<String>()
        if (clv >= 0.70) { score += 20.0; reasons += "strong_close_location" }
        if (baseRangeAtr <= 6.0) { score += 20.0; reasons += "compact_base" }
        if (compression <= 0.85) { score += 20.0; reasons += "volatility_compression" }
        if (touches >= 2) { score += 20.0; reasons += "multiple_resistance_touches" }
        if (latest.close >= priorResistance - touchTolerance) { score += 10.0; reasons += "near_resistance" }
        if (support != null) { score += 10.0; reasons += "relevant_support_identified" }
        if (nextResistance != null) reasons += "relevant_next_resistance_identified"
        return StructureAssessment(
            priorResistance = priorResistance,
            nextResistance = nextResistance,
            support = support,
            swingLow = swingLow,
            closeLocationValue = clv,
            baseRangeAtr = baseRangeAtr,
            volatilityCompression = compression,
            resistanceTouches = touches,
            structureScore = score.coerceIn(0.0, 100.0),
            reasons = reasons
        )
    }

    fun plan(
        entry: Double,
        atr: Double,
        sma20: Double,
        swingLow: Double,
        nextResistance: Double?,
        equity: Double = 25_000.0,
        riskPctOfEquity: Double = 0.01,
        maxPositionPct: Double = 0.20,
        sma50: Double = sma20,
        support: Double? = null,
        setupType: String = "BREAKOUT",
        bars: List<PriceBar> = emptyList()
    ): RiskPlan {
        require(entry > 0 && atr > 0 && equity > 0)
        val buffer = 0.10 * atr
        val previousClose = bars.takeIf { it.size >= 2 }?.let { it[it.lastIndex - 1].close }
        val latestOpen = bars.lastOrNull()?.open
        val gapInvalidation = if (
            previousClose != null && latestOpen != null && latestOpen > previousClose + 0.25 * atr
        ) previousClose - buffer else null

        val raw = listOfNotNull(
            candidate("ATR_STOP", entry - 1.5 * atr, entry, atr, "atr_volatility_invalidation", priority(setupType, "ATR_STOP")),
            candidate("SWING_LOW_STOP", swingLow - buffer, entry, atr, "swing_low_invalidation", priority(setupType, "SWING_LOW_STOP")),
            support?.let { candidate("SUPPORT_STOP", it - buffer, entry, atr, "relevant_support_invalidation", priority(setupType, "SUPPORT_STOP")) },
            candidate("EMA20_STOP", sma20 - buffer, entry, atr, "ema20_trend_invalidation", priority(setupType, "EMA20_STOP")),
            candidate("EMA50_STOP", sma50 - buffer, entry, atr, "ema50_trend_invalidation", priority(setupType, "EMA50_STOP")),
            gapInvalidation?.let { candidate("GAP_INVALIDATION_STOP", it, entry, atr, "opening_gap_fill_invalidation", priority(setupType, "GAP_INVALIDATION_STOP")) }
        ).distinctBy { it.type }

        val validCandidates = raw.filter { it.valid }
        val selected = validCandidates
            .sortedWith(compareByDescending<StopCandidate> { it.setupPriority }.thenBy { it.distanceAtr })
            .firstOrNull()
            ?: candidate(
                "ATR_STOP",
                max(0.01, entry - 1.5 * atr),
                entry,
                atr,
                "atr_fallback_invalidation",
                0
            )
        val stop = selected.price
        val perShareRisk = entry - stop
        val targetByR = entry + 2.5 * perShareRisk
        val relevantResistance = nextResistance?.takeIf { it > entry + 0.25 * atr }
        val target = relevantResistance?.let { min(targetByR, it) } ?: targetByR
        val rr = (target - entry) / perShareRisk
        val riskPct = perShareRisk / entry * 100.0
        val rewardPct = (target - entry) / entry * 100.0
        val budget = equity * riskPctOfEquity
        val sharesByRisk = floor(budget / perShareRisk).toInt().coerceAtLeast(0)
        val sharesByPosition = floor((equity * maxPositionPct) / entry).toInt().coerceAtLeast(0)
        val shares = min(sharesByRisk, sharesByPosition)
        val stopAtrMultiple = perShareRisk / atr
        val reasons = mutableListOf<String>()
        reasons += "selected_${selected.type.lowercase()}"
        reasons += selected.structuralReason
        if (stopAtrMultiple < 0.60) reasons += "stop_too_tight_below_0_6_atr"
        else if (stopAtrMultiple < 1.0) reasons += "aggressive_tight_stop"
        if (stopAtrMultiple > 2.5) reasons += "stop_too_wide"
        if (rr < TradingPolicy.MIN_RR) reasons += "rr_below_min"
        if (shares <= 0) reasons += "position_size_zero"
        if (relevantResistance != null && relevantResistance < targetByR) reasons += "target_capped_by_relevant_resistance"
        if (nextResistance != null && relevantResistance == null) reasons += "near_resistance_blocks_target"
        return RiskPlan(
            entry = entry,
            stop = stop,
            target = target,
            stopType = selected.type,
            stopAtrMultiple = stopAtrMultiple,
            rr = rr,
            riskPct = riskPct,
            rewardPct = rewardPct,
            shares = shares,
            positionValue = shares * entry,
            riskBudget = budget,
            valid = stopAtrMultiple >= 0.60 && rr >= TradingPolicy.MIN_RR && shares > 0 &&
                (nextResistance == null || relevantResistance != null),
            reasons = reasons.distinct(),
            stopCandidates = raw
        )
    }

    private fun candidate(
        type: String,
        price: Double,
        entry: Double,
        atr: Double,
        reason: String,
        priority: Int
    ): StopCandidate {
        val distance = entry - price
        return StopCandidate(
            type = type,
            price = price,
            distanceAtr = distance / atr,
            distancePct = distance / entry * 100.0,
            structuralReason = reason,
            valid = price > 0.0 && price < entry && distance >= 0.40 * atr && distance <= 4.0 * atr,
            setupPriority = priority
        )
    }

    private fun priority(setupType: String, stopType: String): Int {
        val preferred = when (setupType) {
            "BREAKOUT" -> listOf("SUPPORT_STOP", "SWING_LOW_STOP", "ATR_STOP")
            "BREAKOUT_RETEST" -> listOf("SWING_LOW_STOP", "SUPPORT_STOP", "ATR_STOP")
            "PULLBACK_EMA20" -> listOf("EMA20_STOP", "SWING_LOW_STOP", "SUPPORT_STOP")
            "PULLBACK_EMA50" -> listOf("EMA50_STOP", "SWING_LOW_STOP", "SUPPORT_STOP")
            "SUPPORT_RECLAIM" -> listOf("SUPPORT_STOP", "SWING_LOW_STOP", "EMA20_STOP")
            "VOLATILITY_CONTRACTION" -> listOf("SWING_LOW_STOP", "SUPPORT_STOP", "ATR_STOP")
            else -> listOf("SWING_LOW_STOP", "SUPPORT_STOP", "ATR_STOP")
        }
        val index = preferred.indexOf(stopType)
        return if (index < 0) 0 else preferred.size - index
    }

    private fun relevantLevels(values: List<Double>, tolerance: Double, minimumTouches: Int): List<Double> {
        if (values.isEmpty()) return emptyList()
        val sorted = values.sorted()
        val clusters = mutableListOf<MutableList<Double>>()
        sorted.forEach { value ->
            val cluster = clusters.lastOrNull()
            if (cluster == null || abs(value - cluster.average()) > tolerance) {
                clusters += mutableListOf(value)
            } else {
                cluster += value
            }
        }
        return clusters.filter { it.size >= minimumTouches }.map { it.average() }
    }
}
