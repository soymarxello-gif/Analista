package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import com.analista.mobile.data.ScanCandidate
import kotlin.math.max
import kotlin.math.round

object TechnicalEngine {
    fun analyze(ticker: String, bars: List<PriceBar>): ScanCandidate {
        require(bars.size >= 60)
        val closes = bars.map { it.close }; val highs = bars.map { it.high }; val lows = bars.map { it.low }; val volumes = bars.map { it.volume.toDouble() }
        val close = closes.last(); val sma20 = sma(closes, 20); val sma50 = sma(closes, 50); val rsi = rsi(closes, 14)
        val macdSeries = emaSeries(closes, 12).zip(emaSeries(closes, 26)).map { (a, b) -> a - b }
        val macd = macdSeries.last(); val macdSignal = emaSeries(macdSeries, 9).last(); val stochastic = stochastic(highs, lows, closes, 14); val atr = atr(bars, 14)
        val averageVolume = volumes.takeLast(20).dropLast(1).average().takeIf { it > 0 } ?: 1.0
        val relativeVolume = volumes.last() / averageVolume; val prior20High = highs.takeLast(21).dropLast(1).maxOrNull() ?: close
        var score = 0.0; val reasons = mutableListOf<String>()
        if (close > sma20) { score += 15; reasons += "price_above_sma20" }
        if (sma20 > sma50) { score += 20; reasons += "sma20_above_sma50" }
        if (rsi in 50.0..70.0) { score += 15; reasons += "rsi_constructive" }
        if (macd > macdSignal) { score += 15; reasons += "macd_bullish" }
        if (stochastic in 35.0..80.0) { score += 10; reasons += "stochastic_confirmed" }
        if (relativeVolume >= 1.2) { score += 15; reasons += "volume_confirmation" }
        val breakout = close > prior20High
        if (breakout && relativeVolume >= 1.2) { score += 10; reasons += "breakout_confirmed" }
        val overextended = rsi > 75 || close > sma20 + 2.5 * atr
        val signal = when { overextended -> "AVOID"; score >= 80 && breakout -> "TRIGGER_CONFIRMED"; score >= 65 -> "READY_WAIT_TRIGGER"; score >= 50 -> "WATCHLIST"; else -> "AVOID" }
        if (overextended) reasons += "overextended"
        val actionable = signal == "TRIGGER_CONFIRMED" || signal == "READY_WAIT_TRIGGER"
        val entry = if (actionable) close else null; val stop = if (actionable) max(0.01, close - 1.5 * atr) else null
        val target = if (actionable && stop != null) close + 2.5 * (close - stop) else null
        val rr = if (entry != null && stop != null && target != null) (target - entry) / (entry - stop) else null
        return ScanCandidate(ticker.uppercase(), signal, round2(score), round2(close), round2(sma20), round2(sma50), round2(rsi), round4(macd), round4(macdSignal), round2(stochastic), round2(atr), round2(relativeVolume), entry?.let(::round2), stop?.let(::round2), target?.let(::round2), rr?.let(::round2), reasons.joinToString(","))
    }
    fun sma(values: List<Double>, period: Int) = values.takeLast(period).average()
    fun emaSeries(values: List<Double>, period: Int): List<Double> {
        val alpha = 2.0 / (period + 1.0); var previous = values.first(); return values.mapIndexed { index, value -> previous = if (index == 0) value else alpha * value + (1 - alpha) * previous; previous }
    }
    fun rsi(values: List<Double>, period: Int): Double {
        val changes = values.zipWithNext { a, b -> b - a }.takeLast(period); val gains = changes.sumOf { max(it, 0.0) } / period; val losses = changes.sumOf { max(-it, 0.0) } / period
        return if (losses == 0.0) 100.0 else 100.0 - 100.0 / (1.0 + gains / losses)
    }
    fun stochastic(highs: List<Double>, lows: List<Double>, closes: List<Double>, period: Int): Double {
        val high = highs.takeLast(period).maxOrNull() ?: closes.last(); val low = lows.takeLast(period).minOrNull() ?: closes.last(); return if (high == low) 50.0 else 100.0 * (closes.last() - low) / (high - low)
    }
    fun atr(bars: List<PriceBar>, period: Int): Double = bars.zipWithNext { previous, current -> max(current.high - current.low, max(kotlin.math.abs(current.high - previous.close), kotlin.math.abs(current.low - previous.close))) }.takeLast(period).average()
    private fun round2(value: Double) = round(value * 100.0) / 100.0
    private fun round4(value: Double) = round(value * 10000.0) / 10000.0
}
