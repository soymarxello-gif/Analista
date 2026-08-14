package com.analista.mobile.domain

import com.analista.mobile.data.CanonicalAnalysis
import com.analista.mobile.data.PriceBar
import com.analista.mobile.data.ScanCandidate
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.round

object CanonicalAnalysisEngine {
    const val ENGINE_VERSION = "android-v2-canonical-2"

    fun evaluate(bars: List<PriceBar>, candidate: ScanCandidate): CanonicalAnalysis {
        require(bars.size >= 220) { "At least 220 daily bars are required for EMA200" }
        val closes = bars.map { it.close }
        val rsi6 = rsiWilder(closes, 6)
        val rsi14 = rsiWilder(closes, 14)
        val ema20 = emaLast(closes, 20)
        val ema50 = emaLast(closes, 50)
        val ema200 = emaLast(closes, 200)
        val (macd, signal) = macd(closes)
        val atr14 = atrWilder(bars, 14)
        val close = closes.last()
        val weeklyTrend = weeklyTrend(bars)
        val stopAtrMultiple = if (candidate.theoreticalEntry != null && candidate.theoreticalStop != null && atr14 > 0) {
            abs(candidate.theoreticalEntry - candidate.theoreticalStop) / atr14
        } else 0.0
        val stopAtrStatus = when {
            stopAtrMultiple < 0.60 -> "TOO_TIGHT"
            stopAtrMultiple < 1.00 -> "AGGRESSIVE"
            stopAtrMultiple <= 2.50 -> "PREFERRED"
            else -> "TOO_WIDE"
        }

        val trendPoints = listOf(
            close > ema20,
            ema20 > ema50,
            ema50 > ema200,
            weeklyTrend == "UP"
        ).count { it } * 15.0
        val momentumPoints = listOf(
            rsi14 in 50.0..70.0,
            rsi6 > rsi14,
            macd > signal
        ).count { it } * (40.0 / 3.0)
        val assetQuality = (trendPoints + momentumPoints).coerceIn(0.0, 100.0)

        var setupQuality = 0.0
        if (candidate.close > candidate.sma20) setupQuality += 15.0
        if (candidate.sma20 > candidate.sma50) setupQuality += 15.0
        if (candidate.relativeVolume >= 1.2) setupQuality += 20.0
        if (candidate.triggerConfirmed) setupQuality += 25.0
        if (candidate.actionabilityAtExecution == "ACTIONABLE_REVIEW") setupQuality += 25.0
        setupQuality = setupQuality.coerceIn(0.0, 100.0)

        val rr = candidate.rr ?: 0.0
        var riskScore = when {
            rr >= 3.0 -> 100.0
            rr >= 2.5 -> 85.0
            rr >= 2.0 -> 70.0
            rr >= 1.5 -> 45.0
            else -> 20.0
        }
        riskScore += when (stopAtrStatus) {
            "PREFERRED" -> 0.0
            "AGGRESSIVE" -> -10.0
            "TOO_WIDE" -> -20.0
            else -> -35.0
        }
        riskScore = riskScore.coerceIn(0.0, 100.0)

        // Selection is technical-only. Context fields remain visible downstream as
        // advisory evidence and cannot change this score.
        val contextScore = 50.0
        val institutionalScore = 50.0
        var finalTrade = 0.3125 * assetQuality + 0.50 * setupQuality + 0.1875 * riskScore
        if (candidate.signal == "VETO" || candidate.setupType == "NO_VALID_SETUP") finalTrade = minOf(finalTrade, 49.0)
        if (candidate.executionQuoteQuality == "LOW") finalTrade -= 10.0
        if (candidate.penaltyReasons.isNotEmpty()) finalTrade -= minOf(15.0, candidate.penaltyReasons.size * 3.0)
        finalTrade = finalTrade.coerceIn(0.0, 100.0)

        val breakdown = listOf(
            "asset=${round2(assetQuality)}",
            "setup=${round2(setupQuality)}",
            "risk=${round2(riskScore)}",
            "selection=TECHNICAL_SETUP_ONLY",
            "context=ADVISORY_ONLY",
            "institutional=ADVISORY_ONLY"
        ).joinToString(";")

        return CanonicalAnalysis(
            rsi6 = round2(rsi6), rsi14 = round2(rsi14), ema20 = round2(ema20),
            ema50 = round2(ema50), ema200 = round2(ema200), macd = round4(macd),
            macdSignal = round4(signal), atr14 = round2(atr14), weeklyTrend = weeklyTrend,
            assetQualityScore = round2(assetQuality), setupQualityScore = round2(setupQuality),
            contextScore = contextScore, institutionalScore = institutionalScore,
            riskScore = round2(riskScore), finalTradeScore = round2(finalTrade),
            stopAtrMultiple = round2(stopAtrMultiple), stopAtrStatus = stopAtrStatus,
            scoreBreakdown = breakdown
        )
    }

    fun emaLast(values: List<Double>, period: Int): Double = emaSeries(values, period).last()

    fun emaSeries(values: List<Double>, period: Int): List<Double> {
        require(period > 0 && values.size >= period)
        val alpha = 2.0 / (period + 1.0)
        val result = MutableList(values.size) { Double.NaN }
        var previous = values.take(period).average()
        result[period - 1] = previous
        for (index in period until values.size) {
            previous = alpha * values[index] + (1.0 - alpha) * previous
            result[index] = previous
        }
        return result
    }

    fun rsiWilder(values: List<Double>, period: Int): Double {
        require(values.size > period)
        val changes = values.zipWithNext { a, b -> b - a }
        var avgGain = changes.take(period).sumOf { max(it, 0.0) } / period
        var avgLoss = changes.take(period).sumOf { max(-it, 0.0) } / period
        for (change in changes.drop(period)) {
            avgGain = ((period - 1) * avgGain + max(change, 0.0)) / period
            avgLoss = ((period - 1) * avgLoss + max(-change, 0.0)) / period
        }
        if (avgLoss == 0.0) return 100.0
        val rs = avgGain / avgLoss
        return 100.0 - 100.0 / (1.0 + rs)
    }

    fun atrWilder(bars: List<PriceBar>, period: Int): Double {
        require(bars.size > period)
        val trueRanges = bars.mapIndexed { index, bar ->
            if (index == 0) bar.high - bar.low else {
                val previousClose = bars[index - 1].close
                max(bar.high - bar.low, max(abs(bar.high - previousClose), abs(bar.low - previousClose)))
            }
        }
        var atr = trueRanges.take(period).average()
        for (tr in trueRanges.drop(period)) atr = ((period - 1) * atr + tr) / period
        return atr
    }

    fun macd(values: List<Double>): Pair<Double, Double> {
        val ema12 = emaSeries(values, 12)
        val ema26 = emaSeries(values, 26)
        val macdValues = (25 until values.size).map { ema12[it] - ema26[it] }
        val signalSeries = emaSeries(macdValues, 9)
        return macdValues.last() to signalSeries.last()
    }

    fun weeklyTrend(bars: List<PriceBar>): String {
        val weekly = bars
            .groupBy {
                java.time.Instant.ofEpochSecond(it.epochSeconds)
                    .atZone(java.time.ZoneOffset.UTC)
                    .toLocalDate()
                    .with(java.time.temporal.TemporalAdjusters.nextOrSame(java.time.DayOfWeek.FRIDAY))
            }
            .toSortedMap()
            .values
            .map { sessions -> sessions.maxBy { it.epochSeconds }.close }
        if (weekly.size < 30) return "UNKNOWN"
        val ema10 = emaLast(weekly, 10)
        val ema30 = emaLast(weekly, 30)
        return when {
            weekly.last() > ema10 && ema10 > ema30 -> "UP"
            weekly.last() < ema10 && ema10 < ema30 -> "DOWN"
            else -> "SIDEWAYS"
        }
    }

    private fun round2(value: Double) = round(value * 100.0) / 100.0
    private fun round4(value: Double) = round(value * 10000.0) / 10000.0
}
