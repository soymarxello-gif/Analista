package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min

object StructureRiskEngine {
    data class StructureAssessment(
        val priorResistance: Double,
        val nextResistance: Double?,
        val swingLow: Double,
        val closeLocationValue: Double,
        val baseRangeAtr: Double,
        val volatilityCompression: Double,
        val resistanceTouches: Int,
        val structureScore: Double,
        val reasons: List<String>
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
        val reasons: List<String>
    )

    fun assess(bars: List<PriceBar>, atr: Double): StructureAssessment {
        require(bars.size >= 60)
        require(atr > 0.0)
        val latest = bars.last()
        val prior = bars.dropLast(1)
        val resistanceWindow = prior.takeLast(60)
        val priorResistance = resistanceWindow.maxOf { it.high }
        val futureResistance = resistanceWindow.map { it.high }.filter { it > latest.close }.minOrNull()
        val swingLow = prior.takeLast(20).minOf { it.low }
        val range = max(0.000001, latest.high - latest.low)
        val clv = ((latest.close - latest.low) / range).coerceIn(0.0, 1.0)
        val base = prior.takeLast(20)
        val baseRangeAtr = (base.maxOf { it.high } - base.minOf { it.low }) / atr
        val recentAtrProxy = prior.takeLast(10).map { it.high - it.low }.average()
        val priorAtrProxy = prior.takeLast(30).dropLast(10).map { it.high - it.low }.average().takeIf { it > 0 } ?: recentAtrProxy
        val compression = (recentAtrProxy / priorAtrProxy).coerceAtLeast(0.0)
        val touchTolerance = max(0.25 * atr, priorResistance * 0.005)
        val touches = resistanceWindow.count { kotlin.math.abs(it.high - priorResistance) <= touchTolerance }
        var score = 0.0
        val reasons = mutableListOf<String>()
        if (clv >= 0.70) { score += 25.0; reasons += "strong_close_location" }
        if (baseRangeAtr <= 6.0) { score += 20.0; reasons += "compact_base" }
        if (compression <= 0.85) { score += 20.0; reasons += "volatility_compression" }
        if (touches >= 2) { score += 20.0; reasons += "multiple_resistance_touches" }
        if (latest.close >= priorResistance - touchTolerance) { score += 15.0; reasons += "near_resistance" }
        return StructureAssessment(
            priorResistance = priorResistance,
            nextResistance = futureResistance,
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
        maxPositionPct: Double = 0.20
    ): RiskPlan {
        require(entry > 0 && atr > 0 && equity > 0)
        val atrStop = entry - 1.5 * atr
        val structuralStop = min(sma20, swingLow) - 0.10 * atr
        val stopCandidates = listOf("ATR" to atrStop, "STRUCTURE" to structuralStop)
            .filter { it.second > 0 && it.second < entry }
        val selected = stopCandidates.maxByOrNull { it.second } ?: ("ATR" to max(0.01, atrStop))
        val stop = selected.second
        val perShareRisk = entry - stop
        val targetByR = entry + 2.5 * perShareRisk
        val target = nextResistance?.takeIf { it > entry }?.let { min(targetByR, it) } ?: targetByR
        val rr = (target - entry) / perShareRisk
        val riskPct = perShareRisk / entry * 100.0
        val rewardPct = (target - entry) / entry * 100.0
        val budget = equity * riskPctOfEquity
        val sharesByRisk = floor(budget / perShareRisk).toInt().coerceAtLeast(0)
        val sharesByPosition = floor((equity * maxPositionPct) / entry).toInt().coerceAtLeast(0)
        val shares = min(sharesByRisk, sharesByPosition)
        val stopAtrMultiple = perShareRisk / atr
        val reasons = mutableListOf<String>()
        if (stopAtrMultiple < 0.60) reasons += "stop_too_tight_below_0_6_atr"
        else if (stopAtrMultiple < 1.0) reasons += "aggressive_tight_stop"
        if (stopAtrMultiple > 2.5) reasons += "stop_too_wide"
        if (rr < TradingPolicy.MIN_RR) reasons += "rr_below_min"
        if (shares <= 0) reasons += "position_size_zero"
        if (nextResistance != null && nextResistance < targetByR) reasons += "target_capped_by_resistance"
        return RiskPlan(
            entry = entry,
            stop = stop,
            target = target,
            stopType = selected.first,
            stopAtrMultiple = stopAtrMultiple,
            rr = rr,
            riskPct = riskPct,
            rewardPct = rewardPct,
            shares = shares,
            positionValue = shares * entry,
            riskBudget = budget,
            valid = stopAtrMultiple >= 0.60 && rr >= TradingPolicy.MIN_RR && shares > 0,
            reasons = reasons
        )
    }
}
