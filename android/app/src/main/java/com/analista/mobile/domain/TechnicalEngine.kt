package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import com.analista.mobile.data.ScanCandidate
import com.analista.mobile.data.TradeContext
import kotlin.math.max
import kotlin.math.round

object TechnicalEngine {
    fun analyze(
        ticker: String,
        bars: List<PriceBar>,
        context: TradeContext = TradeContext(marketCap = Long.MAX_VALUE)
    ): ScanCandidate {
        require(bars.size >= 60)
        val closes = bars.map { it.close }
        val highs = bars.map { it.high }
        val lows = bars.map { it.low }
        val volumes = bars.map { it.volume.toDouble() }
        val close = closes.last()
        val sma20 = sma(closes, 20)
        val sma50 = sma(closes, 50)
        val rsi = rsi(closes, 14)
        val macdSeries = emaSeries(closes, 12).zip(emaSeries(closes, 26)).map { (a, b) -> a - b }
        val macd = macdSeries.last()
        val macdSignal = emaSeries(macdSeries, 9).last()
        val stochastic = stochastic(highs, lows, closes, 14)
        val atr = atr(bars, 14)
        val averageVolume = volumes.takeLast(20).dropLast(1).average().takeIf { it > 0 } ?: 1.0
        val relativeVolume = volumes.last() / averageVolume
        val prior20High = highs.takeLast(21).dropLast(1).maxOrNull() ?: close

        var score = 0.0
        val reasons = mutableListOf<String>()
        val penalties = mutableListOf<String>()
        val vetoReasons = TradingPolicy.hardVetoReasons(close, context.marketCap, context.quoteType).toMutableList()

        if (close > sma20) { score += 15; reasons += "price_above_sma20" }
        if (sma20 > sma50) { score += 20; reasons += "sma20_above_sma50" }
        if (rsi in 50.0..70.0) { score += 15; reasons += "rsi_constructive" }
        if (macd > macdSignal) { score += 15; reasons += "macd_bullish" }
        if (stochastic in 35.0..80.0) { score += 10; reasons += "stochastic_confirmed" }
        if (relativeVolume >= 1.2) { score += 15; reasons += "volume_confirmation" }

        val breakout = close > prior20High
        val triggerConfirmed = breakout && relativeVolume >= 1.2
        if (triggerConfirmed) { score += 10; reasons += "breakout_confirmed" }

        val overextended = rsi > 75 || close > sma20 + 2.5 * atr
        if (overextended) reasons += "overextended"
        if (context.setupType == "NO_VALID_SETUP") vetoReasons += "no_valid_setup"

        val quote = TradingPolicy.assessQuote(context.quote, close)
        val theoreticalEntry = close
        val theoreticalStop = max(0.01, close - 1.5 * atr)
        val theoreticalTarget = close + 2.5 * (close - theoreticalStop)
        val rr = (theoreticalTarget - theoreticalEntry) / (theoreticalEntry - theoreticalStop)

        var signal = when {
            vetoReasons.isNotEmpty() -> "VETO"
            overextended -> "AVOID"
            triggerConfirmed && score >= 80 -> "TRIGGER_CONFIRMED"
            score >= 65 -> "READY_WAIT_TRIGGER"
            score >= 50 -> "WATCHLIST"
            else -> "AVOID"
        }

        if (signal == "TRIGGER_CONFIRMED" && quote.quality == "LOW") {
            signal = "WATCHLIST"
            penalties += "execution_quote_unconfirmed"
        }
        if (signal == "TRIGGER_CONFIRMED" && rr < TradingPolicy.MIN_RR) {
            signal = "WATCHLIST"
            penalties += "rr_below_min"
        }
        if (signal == "READY_WAIT_TRIGGER" && triggerConfirmed) {
            signal = "WATCHLIST"
            penalties += "trigger_state_incoherent"
        }
        require(signal in TradingPolicy.allowedSignals)

        val actionable = signal == "TRIGGER_CONFIRMED" || signal == "READY_WAIT_TRIGGER"
        val actionableEntry = theoreticalEntry.takeIf { actionable }
        val actionableStop = theoreticalStop.takeIf { actionable }
        val actionableTarget = theoreticalTarget.takeIf { actionable }

        return ScanCandidate(
            ticker = ticker.uppercase(),
            signal = signal,
            score = round2(score),
            close = round2(close),
            sma20 = round2(sma20),
            sma50 = round2(sma50),
            rsi14 = round2(rsi),
            macd = round4(macd),
            macdSignal = round4(macdSignal),
            stochastic = round2(stochastic),
            atr14 = round2(atr),
            relativeVolume = round2(relativeVolume),
            entry = actionableEntry?.let(::round2),
            stop = actionableStop?.let(::round2),
            target = actionableTarget?.let(::round2),
            rr = round2(rr),
            reason = reasons.joinToString(","),
            quoteStatus = quote.status,
            executionQuoteQuality = quote.quality,
            triggerConfirmed = triggerConfirmed,
            setupType = context.setupType,
            allVetoReasons = vetoReasons.distinct(),
            penaltyReasons = penalties.distinct(),
            actionableEntry = actionableEntry?.let(::round2),
            actionableStop = actionableStop?.let(::round2),
            actionableTarget = actionableTarget?.let(::round2),
            theoreticalEntry = round2(theoreticalEntry),
            theoreticalStop = round2(theoreticalStop),
            theoreticalTarget = round2(theoreticalTarget)
        )
    }

    fun sma(values: List<Double>, period: Int) = values.takeLast(period).average()

    fun emaSeries(values: List<Double>, period: Int): List<Double> {
        val alpha = 2.0 / (period + 1.0)
        var previous = values.first()
        return values.mapIndexed { index, value ->
            previous = if (index == 0) value else alpha * value + (1 - alpha) * previous
            previous
        }
    }

    fun rsi(values: List<Double>, period: Int): Double {
        val changes = values.zipWithNext { a, b -> b - a }.takeLast(period)
        val gains = changes.sumOf { max(it, 0.0) } / period
        val losses = changes.sumOf { max(-it, 0.0) } / period
        return if (losses == 0.0) 100.0 else 100.0 - 100.0 / (1.0 + gains / losses)
    }

    fun stochastic(highs: List<Double>, lows: List<Double>, closes: List<Double>, period: Int): Double {
        val high = highs.takeLast(period).maxOrNull() ?: closes.last()
        val low = lows.takeLast(period).minOrNull() ?: closes.last()
        return if (high == low) 50.0 else 100.0 * (closes.last() - low) / (high - low)
    }

    fun atr(bars: List<PriceBar>, period: Int): Double = bars.zipWithNext { previous, current ->
        max(current.high - current.low, max(kotlin.math.abs(current.high - previous.close), kotlin.math.abs(current.low - previous.close)))
    }.takeLast(period).average()

    private fun round2(value: Double) = round(value * 100.0) / 100.0
    private fun round4(value: Double) = round(value * 10000.0) / 10000.0
}
