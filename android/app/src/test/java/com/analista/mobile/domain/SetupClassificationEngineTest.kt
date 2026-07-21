package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SetupClassificationEngineTest {
    private fun bars(
        latestClose: Double = 100.0,
        priorRange: Double = 2.0,
        recentRange: Double = 2.0,
        previousClose: Double = latestClose - 0.1
    ): List<PriceBar> = (0 until 60).map { index ->
        val close = when (index) {
            58 -> previousClose
            59 -> latestClose
            else -> 95.0 + index * 0.08
        }
        val range = if (index >= 50) recentRange else priorRange
        PriceBar(index.toLong(), close - 0.1, close + range / 2.0, close - range / 2.0, close, 1_000_000L)
    }

    private fun input(
        bars: List<PriceBar> = bars(),
        close: Double = bars.last().close,
        sma20: Double = 98.0,
        sma50: Double = 95.0,
        atr: Double = 2.0,
        rsi: Double = 58.0,
        macd: Double = 1.0,
        signal: Double = 0.8,
        rvol: Double = 1.0,
        resistance: Double = 110.0,
        execution: Double? = close
    ) = SetupClassificationEngine.Input(
        bars = bars, close = close, sma20 = sma20, sma50 = sma50, atr = atr,
        rsi14 = rsi, macd = macd, macdSignal = signal, relativeVolume = rvol,
        priorResistance = resistance, executionPrice = execution
    )

    @Test
    fun classifiesDailyBreakoutWithoutRequiringLiveQuote() {
        val result = SetupClassificationEngine.classify(
            input(close = 105.0, rvol = 1.5, resistance = 104.0, execution = null)
        )
        assertEquals("BREAKOUT", result.setupType)
        assertTrue(result.setupValid)
        assertNotNull(result.plannedTrigger)
        assertEquals("RESISTANCE_BUFFER", result.triggerType)
    }

    @Test
    fun classifiesLostPriorBreakoutAsInvalidFailedBreakout() {
        val result = SetupClassificationEngine.classify(
            input(close = 105.0, rvol = 1.5, resistance = 104.0, execution = 103.5)
        )
        assertEquals("FAILED_BREAKOUT", result.setupType)
        assertFalse(result.setupValid)
        assertEquals("LOST_PRIOR_RESISTANCE", result.invalidationType)
    }

    @Test
    fun classifiesConstructiveEma20PullbackFromDailyClose() {
        val result = SetupClassificationEngine.classify(
            input(close = 100.3, sma20 = 100.0, sma50 = 95.0, execution = 110.0, resistance = 120.0)
        )
        assertEquals("PULLBACK_EMA20", result.setupType)
        assertTrue(result.setupValid)
        assertEquals("PULLBACK_BAR_HIGH", result.triggerType)
    }

    @Test
    fun classifiesVolatilityContractionAfterTrend() {
        val compressed = bars(latestClose = 110.0, priorRange = 3.0, recentRange = 0.6, previousClose = 109.8)
        val result = SetupClassificationEngine.classify(
            input(
                bars = compressed, close = 110.0, sma20 = 105.0, sma50 = 100.0,
                execution = null, rvol = 0.8, resistance = 120.0
            )
        )
        assertEquals("VOLATILITY_CONTRACTION", result.setupType)
        assertTrue(result.setupValid)
    }

    @Test
    fun unsupportedStructureIsExplicitlyInvalid() {
        val result = SetupClassificationEngine.classify(
            input(close = 90.0, sma20 = 100.0, sma50 = 105.0, rsi = 35.0, macd = -2.0, signal = -1.0,
                rvol = 0.7, resistance = 110.0, execution = null)
        )
        assertEquals("NO_VALID_SETUP", result.setupType)
        assertFalse(result.setupValid)
        assertEquals("NONE", result.triggerType)
    }
}
