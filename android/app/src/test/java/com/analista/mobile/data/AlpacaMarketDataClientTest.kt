package com.analista.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class AlpacaMarketDataClientTest {
    private val client = AlpacaMarketDataClient()

    @Test
    fun parsesBatchQuotesAndTimestamp() {
        val json = """{
          "quotes": {
            "AAPL": {"ap": 201.15, "bp": 201.10, "t": "2026-07-19T13:19:42.123456Z"},
            "MSFT": {"ap": 0, "bp": 510.20, "t": "2026-07-19T13:19:43Z"}
          }
        }"""
        val result = client.parseLatestQuotes(json, "iex")
        assertEquals(2, result.size)
        assertEquals(201.15, result.getValue("AAPL").ask!!, 0.0001)
        assertEquals(201.10, result.getValue("AAPL").bid!!, 0.0001)
        assertEquals("iex", result.getValue("AAPL").feed)
        assertNull(result.getValue("MSFT").ask)
    }

    @Test
    fun emptyPayloadReturnsEmptyMap() {
        assertEquals(emptyMap<String, AlpacaMarketDataClient.AlpacaQuote>(), client.parseLatestQuotes("{}", "iex"))
    }
}
