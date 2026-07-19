package com.analista.mobile.domain

import com.analista.mobile.data.ReproducibilityManifestEntity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class RunDefinitionFactoryTest {
    @Test
    fun `definition is canonical regardless of universe and configuration order`() {
        val first = RunDefinitionFactory.create(
            runId = "run-1",
            universeName = "default-us-large-cap",
            universeVersion = "1",
            universe = listOf("MSFT", "aapl", "MSFT"),
            configurationVersion = "1",
            configuration = linkedMapOf("risk" to "0.5", "rr" to "2.0"),
            engineBundleVersion = "engines-1",
            manifests = listOf(manifest("AAPL"), manifest("MSFT")),
            createdAtUtc = 10L
        )
        val second = RunDefinitionFactory.create(
            runId = "run-1",
            universeName = "default-us-large-cap",
            universeVersion = "1",
            universe = listOf("AAPL", "MSFT"),
            configurationVersion = "1",
            configuration = linkedMapOf("rr" to "2.0", "risk" to "0.5"),
            engineBundleVersion = "engines-1",
            manifests = listOf(manifest("MSFT"), manifest("AAPL")),
            createdAtUtc = 10L
        )
        assertEquals(first, second)
        assertEquals("AAPL,MSFT", first.universeSymbolsCsv)
        assertEquals("{\"risk\":\"0.5\",\"rr\":\"2.0\"}", first.configurationJson)
    }

    @Test
    fun `inconsistent manifest hashes are rejected`() {
        val inconsistent = manifest("MSFT").copy(configurationHash = "c".repeat(64))
        assertThrows(IllegalArgumentException::class.java) {
            RunDefinitionFactory.create(
                "run-1", "default", "1", listOf("AAPL", "MSFT"), "1", emptyMap(),
                "engines-1", listOf(manifest("AAPL"), inconsistent), 10L
            )
        }
    }

    private fun manifest(ticker: String) = ReproducibilityManifestEntity(
        manifestId = "run-1-$ticker", runId = "run-1", ticker = ticker,
        barsHash = "a".repeat(64), configurationHash = "b".repeat(64),
        universeHash = "d".repeat(64), manifestHash = "e".repeat(64),
        barCount = 100, firstBarTimestampUtc = 1L, lastBarTimestampUtc = 2L,
        provider = "Yahoo", providerHost = "query1.finance.yahoo.com",
        sourceStatus = "AVAILABLE", fallbackUsed = false, cacheHit = false,
        retrievedAtUtc = 3L, engineVersion = "reproducibility-1", createdAtUtc = 4L
    )
}
