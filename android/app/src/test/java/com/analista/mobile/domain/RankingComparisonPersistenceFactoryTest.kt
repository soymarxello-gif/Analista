package com.analista.mobile.domain

import com.analista.mobile.data.CandidateTradePlanEntity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RankingComparisonPersistenceFactoryTest {
    @Test
    fun `empty plans do not create a comparison`() {
        assertNull(RankingComparisonPersistenceFactory.create(emptyList(), 1L))
    }

    @Test
    fun `stable ranks are persisted with adoption status`() {
        val rows = (1..20).map { rank -> plan("T$rank", rank, rank) }
        val entity = RankingComparisonPersistenceFactory.create(rows, 1234L)!!

        assertEquals("run-1", entity.runId)
        assertEquals(20, entity.comparableItems)
        assertEquals(100.0, entity.topKOverlapPct, 0.0)
        assertEquals(1.0, entity.spearman!!, 0.0)
        assertTrue(entity.thresholdsPassed)
        assertEquals("SHADOW_COMPARISON_STABLE", entity.status)
        assertEquals(1234L, entity.calculatedAtUtc)
    }

    @Test
    fun `inverted ranks keep legacy order`() {
        val rows = (1..20).map { rank -> plan("T$rank", rank, 21 - rank) }
        val entity = RankingComparisonPersistenceFactory.create(rows, 1234L)!!

        assertFalse(entity.thresholdsPassed)
        assertEquals("KEEP_LEGACY_ORDER", entity.status)
        assertTrue(entity.reasons.contains("LOW_RANK_CORRELATION"))
    }

    private fun plan(ticker: String, legacyRank: Int, tradeRank: Int) = CandidateTradePlanEntity(
        planId = "run-1-$ticker", runId = "run-1", ticker = ticker,
        priorResistance = 100.0, nextResistance = 110.0, swingLow = 95.0,
        closeLocationValue = 0.8, baseRangeAtr = 2.0, volatilityCompression = 0.7,
        resistanceTouches = 3, structureScore = 70.0, rs20VsSpy = 2.0,
        rs60VsSpy = 4.0, relativeStrengthScore = 65.0, relativeStrengthStatus = "AVAILABLE",
        plannedEntry = 101.0, structuralStop = 96.0, structuralTarget = 111.0,
        stopType = "STRUCTURAL", stopAtrMultiple = 1.5, structuralRr = 2.0,
        riskPct = 4.95, rewardPct = 9.9, shares = 10, positionValue = 1010.0,
        riskBudget = 50.0, riskPlanValid = true, legacyRank = legacyRank,
        tradeRank = tradeRank, rankDelta = legacyRank - tradeRank, auditedTradeScore = 75.0,
        reasons = "", engineVersion = "test", calculatedAtUtc = 1000L
    )
}