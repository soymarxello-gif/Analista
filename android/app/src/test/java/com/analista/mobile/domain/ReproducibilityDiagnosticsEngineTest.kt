package com.analista.mobile.domain

import com.analista.mobile.data.ReproducibilityManifestEntity
import org.junit.Assert.assertEquals
import org.junit.Test

class ReproducibilityDiagnosticsEngineTest {
    @Test
    fun `cobertura completa y hashes consistentes`() {
        val rows = listOf(entity("AAPL"), entity("MSFT"))
        val summary = ReproducibilityDiagnosticsEngine.summarize(2, rows)
        assertEquals("COMPLETE", summary.status)
        assertEquals(100.0, summary.coveragePct, 0.0)
        assertEquals(1, summary.uniqueConfigurationHashes)
        assertEquals(1, summary.uniqueUniverseHashes)
    }

    @Test
    fun `detecta universo inconsistente`() {
        val rows = listOf(entity("AAPL"), entity("MSFT", universeHash = "b".repeat(64)))
        assertEquals("INCONSISTENT", ReproducibilityDiagnosticsEngine.summarize(2, rows).status)
    }

    @Test
    fun `detecta manifiesto invalido antes que cobertura`() {
        val rows = listOf(entity("AAPL").copy(barsHash = "bad"))
        val summary = ReproducibilityDiagnosticsEngine.summarize(1, rows)
        assertEquals("INVALID", summary.status)
        assertEquals(1, summary.invalidManifestCount)
    }

    private fun entity(ticker: String, universeHash: String = "u".repeat(64)) = ReproducibilityManifestEntity(
        manifestId = "run-$ticker", runId = "run", ticker = ticker,
        barsHash = "a".repeat(64), configurationHash = "c".repeat(64),
        universeHash = universeHash, manifestHash = "m".repeat(64), barCount = 200,
        firstBarEpochSeconds = 1L, lastBarEpochSeconds = 2L,
        provider = "YAHOO", providerHost = "query1.finance.yahoo.com",
        providerStatus = "AVAILABLE", fallbackUsed = false, cacheHit = false,
        retrievedAtUtc = 3L, engineVersion = "test"
    )
}
