package com.analista.mobile.domain

import com.analista.mobile.data.MarketQuote
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class QuoteFreshnessEngineTest {
    private val now = 2_000_000L

    private fun quote(timestamp: Long?, state: String = "PRE") = MarketQuote(
        bid = 100.0,
        ask = 100.1,
        regularMarketPrice = 99.0,
        preMarketPrice = 100.05,
        marketCap = 5_000_000_000L,
        quoteType = "EQUITY",
        marketState = state,
        capturedAtUtc = timestamp ?: now,
        providerTimestampUtc = timestamp,
        retrievedAtUtc = now,
        provider = "TEST"
    )

    @Test
    fun freshPremarketQuotePermitsConfirmation() {
        val result = QuoteFreshnessEngine.assess(quote(now - 90_000L), now)
        assertEquals("FRESH", result.status)
        assertEquals(90L, result.ageSeconds)
        assertEquals("PREMARKET", result.marketSession)
        assertTrue(result.executionSessionOpen)
        assertTrue(result.permitsConfirmation)
        assertTrue(result.permitsWaitingContract)
    }

    @Test
    fun delayedQuoteMayWaitButCannotConfirm() {
        val result = QuoteFreshnessEngine.assess(quote(now - 600_000L), now)
        assertEquals("DELAYED_ACCEPTABLE", result.status)
        assertFalse(result.permitsConfirmation)
        assertTrue(result.permitsWaitingContract)
    }

    @Test
    fun freshClosedQuoteIsAnalysisOnly() {
        val result = QuoteFreshnessEngine.assess(quote(now - 30_000L, state = "CLOSED"), now)
        assertEquals("FRESH", result.status)
        assertEquals("CLOSED", result.marketSession)
        assertFalse(result.executionSessionOpen)
        assertFalse(result.permitsConfirmation)
        assertFalse(result.permitsWaitingContract)
        assertTrue("market_session_not_executable" in result.reasons)
    }

    @Test
    fun staleQuoteBlocksEveryContract() {
        val result = QuoteFreshnessEngine.assess(quote(now - 901_000L), now)
        assertEquals("STALE", result.status)
        assertFalse(result.permitsConfirmation)
        assertFalse(result.permitsWaitingContract)
    }

    @Test
    fun missingOrFutureTimestampIsUnknown() {
        val missing = QuoteFreshnessEngine.assess(quote(null), now)
        assertEquals("UNKNOWN", missing.status)
        assertNull(missing.ageSeconds)

        val future = QuoteFreshnessEngine.assess(quote(now + 31_000L), now)
        assertEquals("UNKNOWN", future.status)
        assertFalse(future.permitsWaitingContract)
    }
}
