package com.analista.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
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
    fun parsesActiveTradableEquityAssetsWithoutInventingMetadata() {
        val json = """[
          {"symbol":"AAPL","name":"Apple Inc.","exchange":"NASDAQ","class":"us_equity",
           "status":"active","tradable":true,"fractionable":true,"marginable":true,
           "shortable":true,"easy_to_borrow":true},
          {"symbol":"OLD","exchange":"NYSE","class":"us_equity","status":"inactive","tradable":false}
        ]"""
        val result = client.parseAssets(json)
        assertEquals(2, result.size)
        val apple = result.first()
        assertEquals("AAPL", apple.symbol)
        assertEquals("NASDAQ", apple.exchange)
        assertTrue(apple.tradable)
        assertTrue(apple.fractionable)
        assertFalse(result.last().tradable)
    }

    @Test
    fun parsesGroupedDailyBarsAndPaginationToken() {
        val json = """{
          "bars": {
            "AAPL": [
              {"t":"2026-07-17T04:00:00Z","o":210.0,"h":213.0,"l":209.0,"c":212.5,"v":40000000},
              {"t":"2026-07-20T04:00:00Z","o":212.0,"h":215.0,"l":211.0,"c":214.0,"v":42000000}
            ],
            "EMPTY": []
          },
          "next_page_token": "page-2"
        }"""
        val page = client.parseBarsPage(json)
        assertEquals("page-2", page.nextPageToken)
        assertEquals(2, page.bars.getValue("AAPL").size)
        assertEquals(214.0, page.bars.getValue("AAPL").last().close, 0.0001)
        assertFalse("EMPTY" in page.bars)
    }

    @Test
    fun malformedOrEmptyPayloadsReturnEmptyCollections() {
        assertEquals(emptyMap<String, AlpacaMarketDataClient.AlpacaQuote>(), client.parseLatestQuotes("{}", "iex"))
        val page = client.parseBarsPage("{}")
        assertTrue(page.bars.isEmpty())
        assertNull(page.nextPageToken)
    }
}
