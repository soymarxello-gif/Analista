package com.analista.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class NasdaqScreenerClientTest {
    private val client = NasdaqScreenerClient()

    @Test
    fun parsesMetadataAndMarketCapitalizationFormats() {
        val json = """{
          "data": {"table": {"rows": [
            {"symbol":"META","name":"Meta Platforms, Inc.","marketCap":"1.82T",
             "country":"United States","sector":"Technology","industry":"Internet Services"},
            {"symbol":"TEST.A","name":"Test","marketCap":"2,500,000,000","sector":"Industrials"}
          ]}}
        }"""
        val result = client.parseStocks(json)
        assertEquals(2, result.size)
        assertEquals(1_820_000_000_000L, result.first().marketCap)
        assertEquals("TEST-A", result.last().symbol)
        assertEquals(2_500_000_000L, result.last().marketCap)
    }

    @Test
    fun missingOrInvalidMarketCapRemainsUnknown() {
        assertNull(client.parseMarketCap("N/A"))
        assertNull(client.parseMarketCap("--"))
        assertNull(client.parseMarketCap(null))
        assertEquals(3_500_000_000L, client.parseMarketCap(3_500_000_000L))
    }
}
