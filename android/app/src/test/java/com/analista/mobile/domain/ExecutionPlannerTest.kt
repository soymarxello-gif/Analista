package com.analista.mobile.domain

import com.analista.mobile.data.MarketQuote
import com.analista.mobile.data.PriceBar
import com.analista.mobile.data.TradeContext
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ExecutionPlannerTest {
    private fun bars(): List<PriceBar> = (0 until 90).map { index ->
        val close = 100.0 + index * 0.25
        PriceBar(index.toLong(), close - 0.3, close + 0.6, close - 0.6, close, 1_000_000L + index * 5_000L)
    }

    @Test
    fun excessivePremarketGapCannotRemainActionable() {
        val history = bars()
        val reference = history.last().close
        val quote = MarketQuote(
            bid = reference + 10.0,
            ask = reference + 10.2,
            regularMarketPrice = reference,
            preMarketPrice = reference + 10.1,
            marketCap = 10_000_000_000L,
            quoteType = "EQUITY"
        )
        val result = TechnicalEngine.analyze("TEST", history, TradeContext(quote = quote))
        assertEquals("GAP_EXCESSIVE", result.actionabilityAtExecution)
        assertNull(result.actionableEntry)
        assertTrue("opening_gap_excessive" in result.penaltyReasons)
    }

    @Test
    fun missingQuoteNeverExposesActionableLevels() {
        val result = TechnicalEngine.analyze(
            "TEST",
            bars(),
            TradeContext(quote = null, marketCap = 10_000_000_000L, quoteType = "EQUITY")
        )
        assertEquals("QUOTE_UNCONFIRMED", result.actionabilityAtExecution)
        assertNull(result.actionableEntry)
        assertTrue(result.signal != "TRIGGER_CONFIRMED")
    }
}
