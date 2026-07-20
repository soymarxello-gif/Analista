package com.analista.mobile.domain

import com.analista.mobile.data.AnalyzedCandidate
import com.analista.mobile.data.PriceBar
import com.analista.mobile.data.ScanCandidate
import com.analista.mobile.data.TradeContext
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.round

object TechnicalEngine {
    fun analyzeWithAnalysis(
        ticker: String,
        bars: List<PriceBar>,
        context: TradeContext = TradeContext(marketCap = Long.MAX_VALUE)
    ): AnalyzedCandidate {
        val candidate = analyze(ticker, bars, context)
        return AnalyzedCandidate(candidate, CanonicalAnalysisEngine.evaluate(bars, candidate))
    }

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
        val rsi = CanonicalAnalysisEngine.rsiWilder(closes, 14)
        val (macd, macdSignal) = CanonicalAnalysisEngine.macd(closes)
        val stochastic = stochastic(highs, lows, closes, 14)
        val atr = CanonicalAnalysisEngine.atrWilder(bars, 14)
        val averageVolume = volumes.takeLast(20).dropLast(1).average().takeIf { it > 0 } ?: 1.0
        val relativeVolume = volumes.last() / averageVolume
        val prior20High = highs.takeLast(21).dropLast(1).maxOrNull() ?: close

        var score = 0.0
        val reasons = mutableListOf<String>()
        val penalties = context.dataQualityReasons.toMutableList()
        val vetoReasons = TradingPolicy.hardVetoReasons(close, context.marketCap, context.quoteType).toMutableList()

        if (close > sma20) { score += 15; reasons += "price_above_sma20" }
        if (sma20 > sma50) { score += 20; reasons += "sma20_above_sma50" }
        if (rsi in 50.0..70.0) { score += 15; reasons += "rsi_constructive" }
        if (macd > macdSignal) { score += 15; reasons += "macd_bullish" }
        if (stochastic in 35.0..80.0) { score += 10; reasons += "stochastic_confirmed" }
        if (relativeVolume >= 1.2) { score += 15; reasons += "volume_confirmation" }

        val quote = TradingPolicy.assessQuote(context.quote, close)
        val freshness = QuoteFreshnessEngine.assess(context.quote, context.analysisTimestampUtc)
        penalties += freshness.reasons
        val bid = context.quote?.bid
        val ask = context.quote?.ask
        val livePremarket = context.quote?.preMarketPrice
        val executionPrice = ask ?: livePremarket ?: context.quote?.regularMarketPrice
        val spreadPct = if (bid != null && ask != null && bid > 0 && ask > bid) {
            (ask - bid) / ((ask + bid) / 2.0) * 100.0
        } else null
        val openingGapPct = livePremarket?.let { (it / close - 1.0) * 100.0 }
        val plannedTrigger = prior20High + max(0.25 * atr, prior20High * 0.005)
        val maximumEntry = plannedTrigger + 0.50 * atr
        val priorSessionBreakout = close > prior20High && relativeVolume >= 1.2
        val livePriceInTriggerWindow = executionPrice?.let { it >= plannedTrigger && it <= maximumEntry } ?: false
        val liveTriggerConfirmed = livePriceInTriggerWindow && freshness.permitsConfirmation
        val breakoutHolding = priorSessionBreakout && executionPrice?.let { it >= plannedTrigger } == true
        val failedBreakout = priorSessionBreakout && executionPrice?.let { it < prior20High } == true
        val triggerDistancePct = executionPrice?.let { (it / plannedTrigger - 1.0) * 100.0 }
        val triggerConfirmed = liveTriggerConfirmed && quote.quality != "LOW" && context.executionDataAllowed
        if (priorSessionBreakout) reasons += "prior_session_breakout"
        if (triggerConfirmed) { score += 10; reasons += "live_breakout_confirmed" }
        if (failedBreakout) reasons += "failed_breakout"

        val gapAtr = livePremarket?.let { abs(it - close) / atr }
        val actionability = when {
            vetoReasons.isNotEmpty() -> "VETOED"
            !context.executionDataAllowed && context.dataQualityStatus == "UNUSABLE" -> "DATA_UNUSABLE"
            !context.executionDataAllowed -> "STALE_OR_ILLIQUID_DATA"
            quote.quality == "LOW" -> "QUOTE_UNCONFIRMED"
            executionPrice == null -> "QUOTE_MISSING"
            freshness.status == "STALE" -> "QUOTE_STALE"
            freshness.status == "UNKNOWN" -> "QUOTE_FRESHNESS_UNKNOWN"
            freshness.status == "DELAYED_ACCEPTABLE" && livePriceInTriggerWindow -> "QUOTE_DELAYED"
            gapAtr != null && gapAtr > 1.5 -> "GAP_EXCESSIVE"
            executionPrice > maximumEntry -> "ABOVE_MAX_ENTRY"
            failedBreakout -> "FAILED_BREAKOUT"
            executionPrice < plannedTrigger -> "WAIT_TRIGGER"
            triggerConfirmed -> "ACTIONABLE_REVIEW"
            else -> "WAIT_TRIGGER"
        }
        if (actionability == "GAP_EXCESSIVE") penalties += "opening_gap_excessive"
        if (actionability == "ABOVE_MAX_ENTRY") penalties += "above_maximum_entry"
        if (actionability == "FAILED_BREAKOUT") penalties += "failed_breakout"
        if (actionability == "DATA_UNUSABLE") penalties += "execution_data_unusable"
        if (actionability == "STALE_OR_ILLIQUID_DATA") penalties += "execution_data_unconfirmed"
        if (actionability == "QUOTE_STALE") penalties += "quote_stale_blocks_execution"
        if (actionability == "QUOTE_FRESHNESS_UNKNOWN") penalties += "quote_freshness_unknown"
        if (actionability == "QUOTE_DELAYED") penalties += "quote_delayed_blocks_confirmation"

        val overextended = rsi > 75 || close > sma20 + 2.5 * atr
        if (overextended) reasons += "overextended"
        if (context.setupType == "NO_VALID_SETUP") vetoReasons += "no_valid_setup"

        val theoreticalEntry = plannedTrigger
        val theoreticalStop = max(0.01, minOf(sma20, plannedTrigger - 1.5 * atr))
        val theoreticalTarget = plannedTrigger + 2.5 * (plannedTrigger - theoreticalStop)
        val theoreticalRr = (theoreticalTarget - theoreticalEntry) / (theoreticalEntry - theoreticalStop)
        val executableEntry = executionPrice?.takeIf { actionability == "ACTIONABLE_REVIEW" }
        val executableRr = executableEntry?.let { (theoreticalTarget - it) / (it - theoreticalStop) }
        val rr = executableRr ?: theoreticalRr

        var signal = when {
            vetoReasons.isNotEmpty() -> "VETO"
            overextended || failedBreakout -> "AVOID"
            triggerConfirmed && score >= 80 -> "TRIGGER_CONFIRMED"
            score >= 65 -> "READY_WAIT_TRIGGER"
            score >= 50 -> "WATCHLIST"
            else -> "AVOID"
        }
        if (!context.executionDataAllowed && signal in setOf("TRIGGER_CONFIRMED", "READY_WAIT_TRIGGER")) {
            signal = "WATCHLIST"
            penalties += "data_quality_blocks_execution"
        }
        if (!freshness.permitsWaitingContract && signal in setOf("TRIGGER_CONFIRMED", "READY_WAIT_TRIGGER")) {
            signal = "WATCHLIST"
            penalties += "quote_freshness_blocks_contract"
        }
        if (signal == "TRIGGER_CONFIRMED" && actionability != "ACTIONABLE_REVIEW") {
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

        val actionable = signal == "TRIGGER_CONFIRMED" && actionability == "ACTIONABLE_REVIEW"
        val actionableEntry = executableEntry.takeIf { actionable }
        val actionableStop = theoreticalStop.takeIf { actionable }
        val actionableTarget = theoreticalTarget.takeIf { actionable }

        return ScanCandidate(
            ticker = ticker.uppercase(), signal = signal, score = round2(score), close = round2(close),
            sma20 = round2(sma20), sma50 = round2(sma50), rsi14 = round2(rsi),
            macd = round4(macd), macdSignal = round4(macdSignal), stochastic = round2(stochastic),
            atr14 = round2(atr), relativeVolume = round2(relativeVolume),
            entry = actionableEntry?.let(::round2), stop = actionableStop?.let(::round2),
            target = actionableTarget?.let(::round2), rr = round2(rr), reason = reasons.joinToString(","),
            quoteStatus = quote.status, executionQuoteQuality = quote.quality,
            triggerConfirmed = triggerConfirmed, setupType = context.setupType,
            allVetoReasons = vetoReasons.distinct(), penaltyReasons = penalties.distinct(),
            actionableEntry = actionableEntry?.let(::round2), actionableStop = actionableStop?.let(::round2),
            actionableTarget = actionableTarget?.let(::round2), theoreticalEntry = round2(theoreticalEntry),
            theoreticalStop = round2(theoreticalStop), theoreticalTarget = round2(theoreticalTarget),
            referenceClose = round2(close), livePremarketPrice = livePremarket?.let(::round2),
            bid = bid?.let(::round2), ask = ask?.let(::round2), spreadPct = spreadPct?.let(::round2),
            openingGapPct = openingGapPct?.let(::round2), plannedTrigger = round2(plannedTrigger),
            maximumEntry = round2(maximumEntry), actionabilityAtExecution = actionability,
            quoteCapturedAtUtc = context.quote?.capturedAtUtc,
            priorSessionBreakout = priorSessionBreakout,
            liveTriggerConfirmed = liveTriggerConfirmed,
            breakoutHolding = breakoutHolding,
            failedBreakout = failedBreakout,
            executionPrice = executionPrice?.let(::round2),
            triggerDistancePct = triggerDistancePct?.let(::round2),
            quoteFreshnessStatus = freshness.status,
            quoteAgeSeconds = freshness.ageSeconds,
            quoteProviderTimestampUtc = context.quote?.providerTimestampUtc,
            quoteRetrievedAtUtc = context.quote?.retrievedAtUtc,
            marketSession = freshness.marketSession
        )
    }

    fun sma(values: List<Double>, period: Int) = values.takeLast(period).average()

    fun emaSeries(values: List<Double>, period: Int): List<Double> =
        CanonicalAnalysisEngine.emaSeries(values, period)

    fun rsi(values: List<Double>, period: Int): Double =
        CanonicalAnalysisEngine.rsiWilder(values, period)

    fun stochastic(highs: List<Double>, lows: List<Double>, closes: List<Double>, period: Int): Double {
        val high = highs.takeLast(period).maxOrNull() ?: closes.last()
        val low = lows.takeLast(period).minOrNull() ?: closes.last()
        return if (high == low) 50.0 else 100.0 * (closes.last() - low) / (high - low)
    }

    fun atr(bars: List<PriceBar>, period: Int): Double =
        CanonicalAnalysisEngine.atrWilder(bars, period)

    private fun round2(value: Double) = round(value * 100.0) / 100.0
    private fun round4(value: Double) = round(value * 10000.0) / 10000.0
}
