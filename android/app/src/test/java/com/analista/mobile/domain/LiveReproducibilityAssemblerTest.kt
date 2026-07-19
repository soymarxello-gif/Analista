package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LiveReproducibilityAssemblerTest {
    @Test
    fun `ensambla manifiestos ordenados y consistentes`() {
        val manifests = LiveReproducibilityAssembler.assemble(
            runId = "run-1",
            universe = listOf("MSFT", "AAPL"),
            inputs = listOf(input("MSFT", false, 0), input("AAPL", true, 1))
        )
        assertEquals(listOf("AAPL", "MSFT"), manifests.map { it.ticker })
        assertEquals(1, manifests.map { it.configurationHash }.distinct().size)
        assertEquals(1, manifests.map { it.universeHash }.distinct().size)
        assertTrue(manifests.first { it.ticker == "AAPL" }.cacheHit)
        assertTrue(manifests.first { it.ticker == "AAPL" }.fallbackUsed)
    }

    @Test
    fun `cambio de barra altera solo el manifiesto afectado`() {
        val first = LiveReproducibilityAssembler.assemble("run-1", listOf("AAPL"), listOf(input("AAPL", false, 0))).single()
        val changed = input("AAPL", false, 0).copy(bars = bars().dropLast(1) + bars().last().copy(close = 102.5))
        val second = LiveReproducibilityAssembler.assemble("run-1", listOf("AAPL"), listOf(changed)).single()
        assertNotEquals(first.barsHash, second.barsHash)
        assertNotEquals(first.manifestHash, second.manifestHash)
    }

    @Test(expected = IllegalArgumentException::class)
    fun `rechaza tickers duplicados`() {
        LiveReproducibilityAssembler.assemble("run-1", listOf("AAPL"), listOf(input("AAPL", false, 0), input("aapl", false, 0)))
    }

    private fun input(ticker: String, cache: Boolean, retries: Int) = LiveReproducibilityAssembler.TickerInput(
        ticker = ticker,
        bars = bars(),
        dataQualityStatus = "HIGH",
        cacheHit = cache,
        retries = retries,
        retrievedAtUtc = 1_700_100_000_000L
    )

    private fun bars() = listOf(
        PriceBar(1_700_000_000L, 100.0, 102.0, 99.0, 101.0, 1_000_000L),
        PriceBar(1_700_086_400L, 101.0, 103.0, 100.0, 102.0, 1_100_000L)
    )
}
