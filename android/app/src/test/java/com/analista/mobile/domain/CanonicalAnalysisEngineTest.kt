package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import com.analista.mobile.data.TradeContext
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CanonicalAnalysisEngineTest {
    private fun bars(count: Int = 240): List<PriceBar> = (0 until count).map { index ->
        val close = 80.0 + index * 0.20 + if (index % 11 == 0) -0.4 else 0.0
        PriceBar(
            epochSeconds = index.toLong(),
            open = close - 0.25,
            high = close + 1.0,
            low = close - 1.0,
            close = close,
            volume = 1_000_000L + index * 2_000L
        )
    }

    @Test
    fun emaUsesSmaSeed() {
        val values = (1..10).map(Int::toDouble)
        val series = CanonicalAnalysisEngine.emaSeries(values, 3)
        assertEquals(2.0, series[2], 0.000001)
        assertEquals(9.0, series.last(), 0.000001)
    }

    @Test
    fun wilderRsiForStrictUptrendIsOneHundred() {
        val values = (1..40).map(Int::toDouble)
        assertEquals(100.0, CanonicalAnalysisEngine.rsiWilder(values, 14), 0.000001)
    }

    @Test
    fun wilderAtrUsesTrueRangeRecurrence() {
        val constant = (0 until 40).map { index ->
            PriceBar(index.toLong(), 99.5, 101.0, 99.0, 100.0, 1_000_000L)
        }
        assertEquals(2.0, CanonicalAnalysisEngine.atrWilder(constant, 14), 0.000001)
    }

    @Test
    fun noValidSetupIsAvoidAndCapsFinalTradeScore() {
        val analyzed = TechnicalEngine.analyzeWithAnalysis(
            "TEST",
            bars(),
            TradeContext(marketCap = 10_000_000_000L, quoteType = "EQUITY", setupType = "NO_VALID_SETUP")
        )
        assertEquals("AVOID", analyzed.candidate.signal)
        assertTrue(analyzed.analysis.finalTradeScore <= 49.0)
        assertTrue(analyzed.analysis.ema20 > analyzed.analysis.ema50)
        assertTrue(analyzed.analysis.ema50 > analyzed.analysis.ema200)
    }
}
