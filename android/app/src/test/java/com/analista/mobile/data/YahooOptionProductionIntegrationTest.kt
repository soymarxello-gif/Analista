package com.analista.mobile.data

import android.content.Context
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.kotlin.mock

class YahooOptionProductionIntegrationTest {
    private val client = YahooFinanceClient(mock<Context>())

    private fun chainJson(expiry: Long, strike: Double, gamma: Double? = null): String {
        val gammaField = gamma?.let { ",\"gamma\":$it" }.orEmpty()
        return """{
          "optionChain":{"result":[{
            "quote":{"regularMarketPrice":100.0},
            "expirationDates":[1800000000,1800600000,1801200000],
            "options":[{
              "expirationDate":$expiry,
              "calls":[{"strike":$strike,"openInterest":500,"volume":50,"impliedVolatility":0.25$gammaField}],
              "puts":[{"strike":95.0,"openInterest":700,"volume":40,"impliedVolatility":0.30}]
            }]
          }],"error":null}
        }"""
    }

    @Test
    fun mergesExpiriesDeterministicallyAndPreservesAvailableDates() {
        val first = client.parseOptionChain(chainJson(1800000000, 100.0), "TEST", 100L)
        val second = client.parseOptionChain(chainJson(1800600000, 105.0, 0.02), "TEST", 200L)
        val merged = client.mergeOptionChains(listOf(second, first))
        assertEquals(listOf(1800000000L, 1800600000L), merged.expiries.map { it.expiryEpochSeconds })
        assertEquals(listOf(1800000000L, 1800600000L, 1801200000L), merged.availableExpiries)
        assertEquals(200L, merged.capturedAtUtc)
        assertEquals("AVAILABLE", merged.gammaStatus)
    }

    @Test
    fun legacyCallUsesNormalizedNearSpotOpenInterestAndRegistersSnapshot() {
        OptionChainRegistry.clear()
        val metrics = client.parseOptions(chainJson(1800000000, 115.0), "TEST")
        assertEquals(700L, metrics.nearPutOi)
        assertEquals(null, metrics.nearCallOi)
        val registered = OptionChainRegistry.get("TEST")
        assertNotNull(registered)
        assertTrue(registered!!.expiries.single().contracts.any { it.strike == 115.0 })
    }

    @Test(expected = IllegalArgumentException::class)
    fun refusesToMergeDifferentTickers() {
        val first = client.parseOptionChain(chainJson(1800000000, 100.0), "AAA")
        val second = client.parseOptionChain(chainJson(1800600000, 100.0), "BBB")
        client.mergeOptionChains(listOf(first, second))
    }
}
