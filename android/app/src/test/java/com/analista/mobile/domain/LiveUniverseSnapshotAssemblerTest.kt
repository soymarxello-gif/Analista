package com.analista.mobile.domain

import com.analista.mobile.data.RunUniverseRegistry
import com.analista.mobile.data.UniverseObservationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class LiveUniverseSnapshotAssemblerTest {
    @Before
    fun clear() {
        RunUniverseRegistry.clear()
        UniverseObservationRegistry.clear()
    }

    @Test
    fun usesExactRunUniverseInsteadOfDefaultFallback() {
        RunUniverseRegistry.record("run", listOf("TSM", "AAPL"))
        UniverseObservationRegistry.record(
            UniverseSelectionEngine.Input(
                ticker = "AAPL",
                instrumentType = "EQUITY",
                price = 200.0,
                marketCap = 3_000_000_000_000L,
                averageDollarVolume20 = 1_000_000_000.0,
                spreadPct = 0.05,
                capturedAtUtc = 10L
            )
        )
        val result = LiveUniverseSnapshotAssembler.assemble(
            runId = "run",
            fallbackUniverse = listOf("MSFT"),
            effectiveDate = "2026-07-20",
            createdAtUtc = 100L
        )
        assertEquals(listOf("AAPL", "TSM"), result.universe)
        assertEquals(listOf("AAPL", "TSM"), result.bundle.members.map { it.ticker })
        assertTrue(result.bundle.members.first { it.ticker == "AAPL" }.eligible)
        assertFalse(result.bundle.members.first { it.ticker == "TSM" }.eligible)
        assertTrue(result.bundle.members.first { it.ticker == "TSM" }.exclusionReasons.contains("instrument_type_unverified"))
        assertFalse(result.bundle.members.first { it.ticker == "TSM" }.exclusionReasons.contains("market_cap_below_min"))
        assertEquals("AAPL", result.bundle.snapshot.symbols)
    }

    @Test
    fun liveReproducibilityAssemblerRegistersRequestedUniverseEvenWhenOneTickerFails() {
        val bars = (1..70).map { index ->
            com.analista.mobile.data.PriceBar(index.toLong(), 100.0, 101.0, 99.0, 100.0, 1_000_000L)
        }
        LiveReproducibilityAssembler.assemble(
            runId = "run",
            universe = listOf("AAPL", "FAILED"),
            inputs = listOf(
                LiveReproducibilityAssembler.TickerInput(
                    ticker = "AAPL",
                    bars = bars,
                    dataQualityStatus = "HIGH",
                    cacheHit = false,
                    retries = 0,
                    retrievedAtUtc = 100L
                )
            )
        )
        assertEquals(listOf("AAPL", "FAILED"), RunUniverseRegistry.get("run"))
    }
}
