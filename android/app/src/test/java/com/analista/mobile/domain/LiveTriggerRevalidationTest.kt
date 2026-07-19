package com.analista.mobile.domain

import com.analista.mobile.data.MarketQuote
import com.analista.mobile.data.PriceBar
import com.analista.mobile.data.TradeContext
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class LiveTriggerRevalidationTest {
    private fun breakoutBars(): List<PriceBar> {
        val prior = (0 until 239).map { index ->
            val close = 100.0 + index * 0.08 + if (index % 2 == 0) 0.35 else -0.25
            PriceBar(
                epochSeconds = 1_700_000_000L + index * 86_400L,
                open = close - 0.25,
                high = close + 0.65,
                low = close - 0.65,
                close = close,
                volume = 1_000_000L
            )
        }
        val priorHigh = prior.takeLast(20).maxOf { it.high }
        val close = priorHigh + 1.0
        return prior + PriceBar(
            epochSeconds = 1_700_000_000L + 239 * 86_400L,
            open = close - 0.30,
            high = close + 0.60,
            low = close - 0.70,
            close = close,
            volume = 2_000_000L
        )
    }

    private fun context(price: Double): TradeContext {
        val quote = MarketQuote(
            bid = price - 0.03,
            ask = price,
            regularMarketPrice = price,
            preMarketPrice = price,
            marketCap = 10_000_000_000L,
            quoteType = "EQUITY",
            marketState = "PRE"
        )
        return TradeContext(quote = quote, marketCap = quote.marketCap, quoteType = quote.quoteType)
    }

    @Test
    fun priorSessionBreakoutBelowResistanceIsFailedAndNotConfirmed() {
        val bars = breakoutBars()
        val priorHigh = bars.dropLast(1).takeLast(20).maxOf { it.high }
        val result = TechnicalEngine.analyze("TEST", bars, context(priorHigh - 0.25))

        assertTrue(result.priorSessionBreakout)
        assertTrue(result.failedBreakout)
        assertFalse(result.breakoutHolding)
        assertFalse(result.liveTriggerConfirmed)
        assertFalse(result.triggerConfirmed)
        assertEquals("FAILED_BREAKOUT", result.actionabilityAtExecution)
        assertEquals("AVOID", result.signal)
        assertNull(result.actionableEntry)
    }

    @Test
    fun priceAboveMaximumEntryCannotConfirmTrigger() {
        val bars = breakoutBars()
        val probe = TechnicalEngine.analyze("TEST", bars, context(bars.last().close))
        val price = probe.maximumEntry!! + 0.25
        val result = TechnicalEngine.analyze("TEST", bars, context(price))

        assertFalse(result.liveTriggerConfirmed)
        assertFalse(result.triggerConfirmed)
        assertEquals("ABOVE_MAX_ENTRY", result.actionabilityAtExecution)
        assertNull(result.actionableEntry)
    }

    @Test
    fun priceInsideTriggerWindowConfirmsLiveTrigger() {
        val bars = breakoutBars()
        val probe = TechnicalEngine.analyze("TEST", bars, context(bars.last().close))
        val price = (probe.plannedTrigger!! + probe.maximumEntry!!) / 2.0
        val result = TechnicalEngine.analyze("TEST", bars, context(price))

        assertTrue(result.liveTriggerConfirmed)
        assertTrue(result.triggerConfirmed)
        assertTrue(result.breakoutHolding)
        assertFalse(result.failedBreakout)
        assertEquals("ACTIONABLE_REVIEW", result.actionabilityAtExecution)
    }
}