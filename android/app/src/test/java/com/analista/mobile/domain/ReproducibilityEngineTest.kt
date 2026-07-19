package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class ReproducibilityEngineTest {
    @Test
    fun `bar order does not change canonical hash`() {
        val bars = sampleBars()
        val first = ReproducibilityEngine.createManifest(bars, mapOf("risk" to "1"), listOf("MSFT", "AAPL"))
        val second = ReproducibilityEngine.createManifest(bars.reversed(), mapOf("risk" to "1"), listOf("AAPL", "MSFT"))
        assertEquals(first.barsHash, second.barsHash)
        assertEquals(first.universeHash, second.universeHash)
        assertEquals(first.manifestHash, second.manifestHash)
    }

    @Test
    fun `configuration key order is canonical`() {
        val bars = sampleBars()
        val first = ReproducibilityEngine.createManifest(bars, linkedMapOf("risk" to "1", "rr" to "2"), listOf("AAPL"))
        val second = ReproducibilityEngine.createManifest(bars, linkedMapOf("rr" to "2", "risk" to "1"), listOf("AAPL"))
        assertEquals(first.configurationHash, second.configurationHash)
    }

    @Test
    fun `any price change modifies manifest`() {
        val bars = sampleBars()
        val changed = bars.toMutableList().also { list ->
            val bar = list.last()
            list[list.lastIndex] = bar.copy(close = bar.close + 0.01)
        }
        val first = ReproducibilityEngine.createManifest(bars, emptyMap(), listOf("AAPL"))
        val second = ReproducibilityEngine.createManifest(changed, emptyMap(), listOf("AAPL"))
        assertNotEquals(first.barsHash, second.barsHash)
        assertNotEquals(first.manifestHash, second.manifestHash)
    }

    private fun sampleBars() = listOf(
        PriceBar(1_700_000_000L, 100.0, 102.0, 99.0, 101.0, 1_000_000L),
        PriceBar(1_700_086_400L, 101.0, 103.0, 100.0, 102.0, 1_100_000L)
    )
}
