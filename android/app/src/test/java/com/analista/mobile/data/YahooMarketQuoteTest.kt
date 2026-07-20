package com.analista.mobile.data

import android.content.Context
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.mockito.kotlin.mock

class YahooMarketQuoteTest {
    private val client = YahooFinanceClient(mock<Context>())

    @Test
    fun parsesPremarketExecutionFieldsAndProviderTimestamp() {
        val json = """{
          "quoteResponse": {"result": [{
            "symbol": "TEST",
            "bid": 101.0,
            "ask": 101.2,
            "regularMarketPrice": 100.0,
            "preMarketPrice": 101.1,
            "preMarketTime": 1700000000,
            "regularMarketTime": 1699990000,
            "marketCap": 5000000000,
            "quoteType": "EQUITY",
            "marketState": "PRE"
          }], "error": null}
        }"""
        val retrievedAt = 1_700_000_100_000L
        val quote = client.parseMarketQuote(json, "TEST", retrievedAt)
        assertEquals(101.0, quote.bid!!, 0.0001)
        assertEquals(101.2, quote.ask!!, 0.0001)
        assertEquals(101.1, quote.preMarketPrice!!, 0.0001)
        assertEquals(5_000_000_000L, quote.marketCap)
        assertEquals("EQUITY", quote.quoteType)
        assertEquals("PRE", quote.marketState)
        assertEquals(1_700_000_000_000L, quote.providerTimestampUtc)
        assertEquals(1_700_000_000_000L, quote.capturedAtUtc)
        assertEquals(retrievedAt, quote.retrievedAtUtc)
        assertEquals("YAHOO", quote.provider)
    }

    @Test
    fun missingProviderTimestampRemainsUnknownInsteadOfUsingRetrievalTime() {
        val json = """{"quoteResponse":{"result":[{
          "symbol":"TEST","bid":100,"ask":100.1,"regularMarketPrice":100,
          "marketCap":5000000000,"quoteType":"EQUITY"
        }],"error":null}}"""
        val quote = client.parseMarketQuote(json, "TEST", 1_700_000_100_000L)
        assertNull(quote.providerTimestampUtc)
        assertEquals(1_700_000_100_000L, quote.capturedAtUtc)
    }

    @Test
    fun zeroBidAndAskBecomeMissingValues() {
        val json = """{"quoteResponse":{"result":[{
          "symbol":"TEST","bid":0,"ask":0,"regularMarketPrice":100,
          "marketCap":5000000000,"quoteType":"EQUITY"
        }],"error":null}}"""
        val quote = client.parseMarketQuote(json, "TEST")
        assertNull(quote.bid)
        assertNull(quote.ask)
    }
}
