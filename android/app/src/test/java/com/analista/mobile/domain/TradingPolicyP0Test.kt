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
    private val now = 2_000_000L

    private fun bars(lastClose: Double = 150.0, breakout: Boolean = false): List<PriceBar> {
        val base = (0 until 89).map { index ->
            val close = 100.0 + index * 0.4
            PriceBar(index.toLong(), close - 0.5, close + 0.8, close - 0.8, close, 1_000_000L)
        }
        val priorHigh = base.takeLast(20).maxOf { it.high }
        val close = if (breakout) priorHigh + 2.0 else lastClose
        return base + PriceBar(89, close - 0.5, close + 0.8, close - 0.8, close, 2_000_000L)
    }

    private fun quote(
        marketCap: Long? = 10_000_000_000L,
        type: String? = "EQUITY",
        state: String = "PRE",
        bid: Double = 149.9,
        ask: Double = 150.1
    ) = MarketQuote(
        bid = bid, ask = ask, regularMarketPrice = 150.0, preMarketPrice = 150.0,
        marketCap = marketCap, quoteType = type, marketState = state,
        capturedAtUtc = now - 30_000L, providerTimestampUtc = now - 30_000L,
        retrievedAtUtc = now, provider = "TEST"
    )

    private fun validContext(
        quote: MarketQuote = quote(),
        marketCap: Long? = quote.marketCap,
        setupType: String = "BREAKOUT_OR_PULLBACK"
    ) = TradeContext(
        quote = quote, marketCap = marketCap, quoteType = quote.quoteType,
        setupType = setupType, analysisTimestampUtc = now,
        eligibilityVerified = marketCap != null && !quote.quoteType.isNullOrBlank()
    )

    @Test fun invalidBidAskCannotBeTriggerConfirmed() {
        val result = TechnicalEngine.analyze("TEST", bars(breakout = true), validContext(quote(bid = 151.0, ask = 150.0)))
        assertEquals("LOW", result.executionQuoteQuality)
        assertFalse(result.signal == "TRIGGER_CONFIRMED")
    }

    @Test fun priceFilterIsHard() {
        val result = TechnicalEngine.analyze("TEST", bars(lastClose = 8.0), validContext())
        assertEquals("VETO", result.signal)
        assertTrue("price_below_min" in result.allVetoReasons)
    }

    @Test fun marketCapFilterIsHardOnlyWhenValueIsKnown() {
        val result = TechnicalEngine.analyze("TEST", bars(), validContext(quote(marketCap = 500_000_000L)))
        assertEquals("VETO", result.signal)
        assertTrue("market_cap_below_min" in result.allVetoReasons)
    }

    @Test fun missingMarketCapIsUnverifiedNotFalseVeto() {
        val result = TechnicalEngine.analyze("META", bars(), validContext(quote(marketCap = null)))
        assertFalse("market_cap_below_min" in result.allVetoReasons)
        assertFalse(result.signal == "VETO")
        assertTrue("market_cap_unverified" in result.penaltyReasons)
        assertFalse(result.eligibilityVerified)
    }

    @Test fun etfDoesNotRequireCompanyMarketCap() {
        assertTrue(TradingPolicy.eligibilityVerified(null, "ETF"))
        assertFalse("market_cap_unverified" in TradingPolicy.eligibilityWarnings(null, "ETF"))
        assertFalse("market_cap_below_min" in TradingPolicy.hardVetoReasons(100.0, 0L, "ETF"))
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

    @Test fun noValidSetupIsAvoidNotUniverseVeto() {
        val result = TechnicalEngine.analyze("TEST", bars(), validContext(setupType = "NO_VALID_SETUP"))
        assertEquals("AVOID", result.signal)
        assertTrue(result.allVetoReasons.isEmpty())
        assertTrue("no_valid_setup" in result.penaltyReasons)
    }

    @Test fun closedSessionIsAnalysisOnly() {
        val result = TechnicalEngine.analyze("TEST", bars(breakout = true), validContext(quote(state = "CLOSED")))
        assertEquals("MARKET_CLOSED_ANALYSIS_ONLY", result.actionabilityAtExecution)
        assertFalse(result.executionSessionOpen)
        assertFalse(result.triggerConfirmed)
        assertNull(result.spreadPct)
        assertFalse(result.signal == "TRIGGER_CONFIRMED" || result.signal == "READY_WAIT_TRIGGER")
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
