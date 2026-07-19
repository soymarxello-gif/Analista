package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Test

class ReproducibilityManifestFactoryTest {
    @Test
    fun `crea entidad persistible determinista`() {
        val input = input(listOf("MSFT", "AAPL"))
        val first = ReproducibilityManifestFactory.create(input)
        val second = ReproducibilityManifestFactory.create(input.copy(universe = listOf("AAPL", "MSFT")))

        assertEquals("run-1-AAPL", first.manifestId)
        assertEquals(first.manifestHash, second.manifestHash)
        assertEquals(2, first.barCount)
        assertEquals("YAHOO", first.provider)
        assertFalse(first.fallbackUsed)
    }

    @Test
    fun `cambio de barra cambia manifiesto persistido`() {
        val first = ReproducibilityManifestFactory.create(input(listOf("AAPL")))
        val changedBars = bars().toMutableList().also { list ->
            list[list.lastIndex] = list.last().copy(close = 102.01)
        }
        val second = ReproducibilityManifestFactory.create(input(listOf("AAPL")).copy(bars = changedBars))

        assertNotEquals(first.barsHash, second.barsHash)
        assertNotEquals(first.manifestHash, second.manifestHash)
    }

    @Test(expected = IllegalArgumentException::class)
    fun `rechaza barras vacias`() {
        ReproducibilityManifestFactory.create(input(listOf("AAPL")).copy(bars = emptyList()))
    }

    private fun input(universe: List<String>) = ReproducibilityManifestFactory.Input(
        runId = "run-1",
        ticker = "aapl",
        bars = bars(),
        configuration = mapOf("riskPct" to "1.0", "minRr" to "2.0"),
        universe = universe,
        source = ReproducibilityManifestFactory.SourceMetadata(
            provider = "YAHOO",
            providerHost = "query1.finance.yahoo.com",
            providerStatus = "AVAILABLE",
            fallbackUsed = false,
            cacheHit = false,
            retrievedAtUtc = 1_700_100_000_000L
        )
    )

    private fun bars() = listOf(
        PriceBar(1_700_000_000L, 100.0, 102.0, 99.0, 101.0, 1_000_000L),
        PriceBar(1_700_086_400L, 101.0, 103.0, 100.0, 102.0, 1_100_000L)
    )
}
