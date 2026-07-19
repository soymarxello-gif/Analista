package com.analista.mobile.data

import android.content.Context
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.mockito.kotlin.mock

class YahooMarketQuoteTest {
    private val client = YahooFinanceClient(mock<Context>())

    @Test
    fun parsesPremarketExecutionFields() {
        val json = """{
          "quoteResponse": {"result": [{
            "symbol": "TEST",
            "bid": 101.0,
            "ask": 101.2,
            "regularMarketPrice": 100.0,
            "preMarketPrice": 101.1,
            "marketCap": 5000000000,
            "quoteType": "EQUITY",
            "marketState": "PRE"
          }], "error": null}
        }"""
        val quote = client.parseMarketQuote(json, "TEST")
        assertEquals(101.0, quote.bid!!, 0.0001)
        assertEquals(101.2, quote.ask!!, 0.0001)
        assertEquals(101.1, quote.preMarketPrice!!, 0.0001)
        assertEquals(5_000_000_000L, quote.marketCap)
        assertEquals("EQUITY", quote.quoteType)
        assertEquals("PRE", quote.marketState)
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
