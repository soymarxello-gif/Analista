package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TechnicalEngineTest {
    private fun bars(count: Int = 90): List<PriceBar> = (0 until count).map { index -> val close = 100.0 + index * 0.5; PriceBar(index.toLong(), close - 0.4, close + 1.0, close - 1.0, close, 1_000_000L + index * 10_000L) }
    @Test fun computesIndicatorsAndLongOnlySignal() { val result = TechnicalEngine.analyze("TEST", bars()); assertEquals("TEST", result.ticker); assertTrue(result.sma20 > result.sma50); assertTrue(result.rsi14 >= 50.0); assertTrue(result.signal in setOf("WATCHLIST","READY_WAIT_TRIGGER","TRIGGER_CONFIRMED","AVOID")) }
    @Test fun movingAverageIsDeterministic() { assertEquals(4.0, TechnicalEngine.sma(listOf(1.0,2.0,3.0,4.0,5.0), 3), 0.0001) }
}
