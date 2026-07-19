package com.analista.mobile.domain

import com.analista.mobile.data.MarketQuote
import com.analista.mobile.data.PriceBar
import com.analista.mobile.data.TradeContext
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class TradingPolicyP0Test {
    private fun bars(lastClose: Double = 150.0, breakout: Boolean = false): List<PriceBar> {
        val base = (0 until 89).map { index ->
            val close = 100.0 + index * 0.4
            PriceBar(index.toLong(), close - 0.5, close + 0.8, close - 0.8, close, 1_000_000L)
        }
        val priorHigh = base.takeLast(20).maxOf { it.high }
        val close = if (breakout) priorHigh + 2.0 else lastClose
        return base + PriceBar(89, close - 0.5, close + 0.8, close - 0.8, close, 2_000_000L)
    }

    private fun validContext(
        quote: MarketQuote = MarketQuote(149.9, 150.1, 150.0, 150.0, 10_000_000_000L, "EQUITY"),
        marketCap: Long? = 10_000_000_000L,
        setupType: String = "BREAKOUT_OR_PULLBACK"
    ) = TradeContext(quote = quote, marketCap = marketCap, quoteType = quote.quoteType, setupType = setupType)

    @Test fun invalidBidAskCannotBeTriggerConfirmed() {
        val badQuote = MarketQuote(151.0, 150.0, 150.0, 150.0, 10_000_000_000L, "EQUITY")
        val result = TechnicalEngine.analyze("TEST", bars(breakout = true), validContext(badQuote))
        assertEquals("LOW", result.executionQuoteQuality)
        assertFalse(result.signal == "TRIGGER_CONFIRMED")
    }

    @Test fun priceFilterIsHard() {
        val result = TechnicalEngine.analyze("TEST", bars(lastClose = 8.0), validContext())
        assertEquals("VETO", result.signal)
        assertTrue("price_below_min" in result.allVetoReasons)
    }

    @Test fun marketCapFilterIsHard() {
        val result = TechnicalEngine.analyze("TEST", bars(), validContext(marketCap = 500_000_000L))
        assertEquals("VETO", result.signal)
        assertTrue("market_cap_below_min" in result.allVetoReasons)
    }

    @Test fun readyWaitTriggerRequiresUnconfirmedTrigger() {
        val result = TechnicalEngine.analyze("TEST", bars(), validContext())
        if (result.signal == "READY_WAIT_TRIGGER") assertFalse(result.triggerConfirmed)
    }

    @Test fun triggerConfirmedRequiresQuoteAndRiskReward() {
        val result = TechnicalEngine.analyze("TEST", bars(breakout = true), validContext())
        if (result.signal == "TRIGGER_CONFIRMED") {
            assertTrue(result.triggerConfirmed)
            assertFalse(result.executionQuoteQuality == "LOW")
            assertTrue((result.rr ?: 0.0) >= 2.0)
        }
    }

    @Test fun noValidSetupIsVeto() {
        val result = TechnicalEngine.analyze("TEST", bars(), validContext(setupType = "NO_VALID_SETUP"))
        assertEquals("VETO", result.signal)
        assertTrue("no_valid_setup" in result.allVetoReasons)
    }

    @Test fun vetoHasNoActionableLevels() {
        val result = TechnicalEngine.analyze("TEST", bars(lastClose = 8.0), validContext())
        assertEquals("VETO", result.signal)
        assertNull(result.actionableEntry)
        assertNull(result.actionableStop)
        assertNull(result.actionableTarget)
        assertTrue(result.theoreticalEntry != null)
    }

    @Test fun buySetupActiveIsDisabled() {
        val contexts = listOf(validContext(), validContext(setupType = "NO_VALID_SETUP"))
        contexts.forEach { context ->
            assertFalse(TechnicalEngine.analyze("TEST", bars(breakout = true), context).signal == "BUY_SETUP_ACTIVE")
        }
    }
}
