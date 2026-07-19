package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class RelativeStrengthEngineTest {
    private fun series(step: Double): List<PriceBar> = (0..80).map { i ->
        val close = 100.0 + i * step
        PriceBar(
            epochSeconds = 1_700_000_000L + i * 86_400L,
            open = close,
            high = close + 1.0,
            low = close - 1.0,
            close = close,
            volume = 1_000_000L
        )
    }

    @Test
    fun strongerAssetScoresAboveNeutral() {
        val result = RelativeStrengthEngine.compare(series(0.8), series(0.2))
        assertTrue(result.rs20Pct > 0)
        assertTrue(result.rs60Pct > 0)
        assertTrue(result.score > 50)
        assertTrue(result.status in setOf("POSITIVE", "STRONG"))
    }

    @Test
    fun equalSeriesAreNeutralPositive() {
        val result = RelativeStrengthEngine.compare(series(0.3), series(0.3))
        assertEquals(0.0, result.rs20Pct, 1e-9)
        assertEquals(0.0, result.rs60Pct, 1e-9)
        assertEquals(50.0, result.score, 1e-9)
        assertEquals("POSITIVE", result.status)
    }
}
