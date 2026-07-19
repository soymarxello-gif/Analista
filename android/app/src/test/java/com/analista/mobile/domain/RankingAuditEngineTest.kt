package com.analista.mobile.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RankingAuditEngineTest {
    @Test
    fun vetoCannotBeElevatedByStrongAssetMetrics() {
        val rows = listOf(
            RankingAuditEngine.Input("VETO1", "VETO", "BREAKOUT", 99.0, 98.0, 100.0, 100.0, true),
            RankingAuditEngine.Input("VALID", "WATCHLIST", "PULLBACK", 70.0, 72.0, 70.0, 65.0, true)
        )
        val ranked = RankingAuditEngine.compare(rows)
        val veto = ranked.first { it.ticker == "VETO1" }
        val valid = ranked.first { it.ticker == "VALID" }
        assertFalse(veto.eligibleForOperationalRanking)
        assertTrue(veto.protectedTradeScore <= 49.0)
        assertTrue(valid.tradeRank < veto.tradeRank)
    }

    @Test
    fun noValidSetupCannotBeElevated() {
        val row = RankingAuditEngine.Input("BAD", "WATCHLIST", "NO_VALID_SETUP", 90.0, 90.0, 100.0, 100.0, true)
        val ranked = RankingAuditEngine.compare(listOf(row)).single()
        assertFalse(ranked.eligibleForOperationalRanking)
        assertEquals(49.0, ranked.protectedTradeScore, 0.0001)
    }

    @Test
    fun strongerStructureAndRiskImproveTradeRank() {
        val rows = listOf(
            RankingAuditEngine.Input("A", "WATCHLIST", "BREAKOUT", 80.0, 75.0, 40.0, 45.0, false),
            RankingAuditEngine.Input("B", "WATCHLIST", "PULLBACK", 70.0, 75.0, 85.0, 80.0, true)
        )
        val ranked = RankingAuditEngine.compare(rows)
        val a = ranked.first { it.ticker == "A" }
        val b = ranked.first { it.ticker == "B" }
        assertTrue(b.tradeRank < a.tradeRank)
        assertTrue(b.rankDelta > 0)
    }

    @Test
    fun comparisonIsDeterministicOnTies() {
        val rows = listOf(
            RankingAuditEngine.Input("BBB", "WATCHLIST", "PULLBACK", 70.0, 70.0, 50.0, 50.0, true),
            RankingAuditEngine.Input("AAA", "WATCHLIST", "PULLBACK", 70.0, 70.0, 50.0, 50.0, true)
        )
        val ranked = RankingAuditEngine.compare(rows)
        assertEquals("AAA", ranked.first().ticker)
    }
}
