package com.analista.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class YahooOptionChainParserTest {
    private val json = """{
      "optionChain":{"result":[{
        "quote":{"regularMarketPrice":100.0},
        "expirationDates":[1800000000,1800600000],
        "options":[{
          "expirationDate":1800000000,
          "calls":[
            {"strike":100.0,"bid":2.0,"ask":2.2,"volume":80,"openInterest":500,"impliedVolatility":0.25,"lastTradeDate":1799900000},
            {"strike":115.0,"bid":0.2,"ask":0.3,"openInterest":900}
          ],
          "puts":[
            {"strike":95.0,"bid":1.1,"ask":1.3,"volume":40,"openInterest":750,"impliedVolatility":0.30}
          ]
        }]
      }],"error":null}
    }"""

    @Test
    fun parsesStrikeExpiryVolumeOiAndDistanceToSpot() {
        val chain = YahooOptionChainParser.parse(json, "test", 123L)
        assertEquals("TEST", chain.ticker)
        assertEquals(100.0, chain.spot ?: 0.0, 0.0)
        assertEquals(listOf(1800000000L, 1800600000L), chain.availableExpiries)
        assertEquals(1, chain.expiries.size)
        assertEquals(3, chain.expiries.single().contracts.size)
        val call = chain.expiries.single().contracts.first { it.type == "CALL" && it.strike == 100.0 }
        assertEquals(500L, call.openInterest)
        assertEquals(80L, call.volume)
        assertEquals(0.0, call.distanceToSpotPct ?: 999.0, 0.0001)
        assertEquals("UNKNOWN", chain.gammaStatus)
        assertNull(call.gamma)
    }

    @Test
    fun legacyMetricsUseNearSpotOpenInterestInsteadOfWholeExpiry() {
        val metrics = YahooOptionChainParser.parse(json, "TEST").toLegacyMetrics()
        assertEquals(750.0 / 1400.0, metrics.putCallOi ?: 0.0, 0.0001)
        assertEquals(500L, metrics.nearCallOi)
        assertEquals(750L, metrics.nearPutOi)
        assertEquals(1800000000L, metrics.expiry)
    }

    @Test
    fun missingGreeksRemainUnknownRatherThanEstimated() {
        val chain = YahooOptionChainParser.parse(json, "TEST")
        assertEquals("UNKNOWN", chain.gammaStatus)
        assertTrue(chain.expiries.flatMap { it.contracts }.all { it.gamma == null && it.delta == null })
    }
}
