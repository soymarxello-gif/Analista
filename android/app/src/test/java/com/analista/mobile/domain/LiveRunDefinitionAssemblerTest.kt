package com.analista.mobile.domain

import com.analista.mobile.data.ReproducibilityManifestEntity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LiveRunDefinitionAssemblerTest {
    @Test
    fun `definition reuses manifest hashes and exact normalized universe`() {
        val row = LiveRunDefinitionAssembler.assemble(
            runId = "run-1",
            universe = listOf("msft", "AAPL", "MSFT"),
            manifests = listOf(manifest("AAPL"), manifest("MSFT")),
            engineBundleVersion = "engines-1",
            createdAtUtc = 10L
        )

        assertEquals("AAPL,MSFT", row.universeSymbolsCsv)
        assertEquals("d".repeat(64), row.universeHash)
        assertEquals("b".repeat(64), row.configurationHash)
        assertTrue(row.universeVersion.endsWith("d".repeat(12)))
        assertTrue(row.configurationVersion.endsWith("b".repeat(12)))
        assertTrue(row.engineBundleVersion.contains(LiveRunDefinitionAssembler.VERSION))
    }

    private fun manifest(ticker: String) = ReproducibilityManifestEntity(
        manifestId = "run-1-$ticker",
        runId = "run-1",
        ticker = ticker,
        barsHash = "a".repeat(64),
        configurationHash = "b".repeat(64),
        universeHash = "d".repeat(64),
        manifestHash = "e".repeat(64),
        barCount = 100,
        firstBarEpochSeconds = 1L,
        lastBarEpochSeconds = 2L,
        provider = "YAHOO",
        providerHost = "query1.finance.yahoo.com",
        providerStatus = "AVAILABLE",
        fallbackUsed = false,
        cacheHit = false,
        retrievedAtUtc = 3L,
        engineVersion = "reproducibility-1"
    )
}
