package com.analista.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class ProviderMatrixTest {
    @Before
    fun clear() {
        ProviderMatrixRegistry.clear()
        FundamentalSnapshotRegistry.clear()
        OptionChainRegistry.clear()
        HistorySourceRegistry.clear()
    }

    @Test
    fun policyDefinesModuleSpecificPriorities() {
        assertEquals(listOf("ALPACA", "YAHOO"), ProviderMatrixPolicy.priorities.getValue("EXECUTION_QUOTE"))
        assertEquals(
            listOf("SEC_COMPANYFACTS_BACKEND", "YAHOO_RESEARCH_ONLY"),
            ProviderMatrixPolicy.priorities.getValue("FUNDAMENTAL")
        )
    }

    @Test
    fun unavailableSecondarySourcesAreDeclared() {
        val rows = ProviderMatrixAssembler.forTicker("TEST", 100L)
        val fundamental = rows.first { it.module == "FUNDAMENTAL" }
        assertEquals("UNAVAILABLE", fundamental.status)
        assertEquals(0.0, fundamental.coveragePct, 0.0)
        assertTrue(fundamental.errorStatus!!.contains("SEC_BACKEND_NOT_CONFIGURED"))
        assertTrue(!fundamental.errorStatus!!.contains("TRADINGVIEW"))
    }

    @Test
    fun queryTwoAndCacheAreMarkedAsFallback() {
        HistorySourceRegistry.record("TEST", "Yahoo/query2.finance.yahoo.com")
        val queryTwo = ProviderMatrixAssembler.forTicker("TEST", 100L)
            .first { it.module == "HISTORICAL_PRICE" }
        assertTrue(queryTwo.fallbackUsed)
        assertEquals("query2.finance.yahoo.com", queryTwo.host)

        HistorySourceRegistry.record("TEST", "Yahoo/cache")
        val cache = ProviderMatrixAssembler.forTicker("TEST", 100L)
            .first { it.module == "HISTORICAL_PRICE" }
        assertTrue(cache.fallbackUsed)
        assertEquals("STALE_POSSIBLE", cache.freshness)
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsUnknownModules() {
        ProviderMatrixPolicy.validate(
            ProviderObservation(
                module = "UNKNOWN",
                ticker = "TEST",
                provider = "YAHOO",
                host = "example.com",
                status = "UNAVAILABLE",
                coveragePct = 0.0,
                providerTimestampUtc = null,
                retrievedAtUtc = 1L,
                freshness = "UNKNOWN",
                fallbackUsed = false
            )
        )
    }
}
