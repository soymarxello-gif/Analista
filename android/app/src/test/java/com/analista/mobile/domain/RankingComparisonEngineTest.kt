package com.analista.mobile.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RankingComparisonEngineTest {
    @Test
    fun `rankings idénticos superan umbrales`() {
        val items = (1..25).map { rank ->
            RankingComparisonEngine.Item("T$rank", rank, rank)
        }

        val summary = RankingComparisonEngine.compare(items)

        assertEquals(100.0, summary.topKOverlapPct, 0.0)
        assertEquals(0.0, summary.medianAbsoluteDisplacement ?: -1.0, 0.0)
        assertEquals(1.0, summary.spearman ?: 0.0, 0.0)
        assertTrue(summary.thresholdsPassed)
        assertEquals("SHADOW_COMPARISON_STABLE", summary.status)
    }

    @Test
    fun `inversión de ranking mantiene orden legacy`() {
        val items = (1..25).map { rank ->
            RankingComparisonEngine.Item("T$rank", rank, 26 - rank)
        }

        val summary = RankingComparisonEngine.compare(items)

        assertEquals(-1.0, summary.spearman ?: 0.0, 0.0)
        assertFalse(summary.thresholdsPassed)
        assertEquals("KEEP_LEGACY_ORDER", summary.status)
        assertTrue("LOW_TOP_K_OVERLAP" in summary.reasons)
        assertTrue("LOW_RANK_CORRELATION" in summary.reasons)
    }

    @Test
    fun `faltantes se declaran y bloquean adopción`() {
        val items = (1..20).map { rank ->
            RankingComparisonEngine.Item("T$rank", rank, if (rank == 20) null else rank)
        }

        val summary = RankingComparisonEngine.compare(items)

        assertEquals(1, summary.missingItems)
        assertFalse(summary.thresholdsPassed)
        assertTrue("MISSING_RANKS" in summary.reasons)
        assertTrue("INSUFFICIENT_SAMPLE" in summary.reasons)
    }

    @Test(expected = IllegalArgumentException::class)
    fun `rechaza tickers duplicados`() {
        RankingComparisonEngine.compare(
            listOf(
                RankingComparisonEngine.Item("AAPL", 1, 1),
                RankingComparisonEngine.Item("aapl", 2, 2)
            ),
            RankingComparisonEngine.Thresholds(minimumComparableItems = 2)
        )
    }
}
