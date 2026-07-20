package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class StructureRiskEngineTest {
    private fun bars(count: Int = 80): List<PriceBar> = (0 until count).map { i ->
        val close = 100.0 + i * 0.25
        PriceBar(
            epochSeconds = 1_700_000_000L + i * 86_400L,
            open = close - 0.5,
            high = close + 1.0,
            low = close - 1.0,
            close = if (i == count - 1) close + 0.8 else close,
            volume = 2_000_000L
        )
    }

    @Test
    fun assessmentProducesBoundedStructureMetrics() {
        val result = StructureRiskEngine.assess(bars(), atr = 2.0)
        assertTrue(result.closeLocationValue in 0.0..1.0)
        assertTrue(result.structureScore in 0.0..100.0)
        assertTrue(result.swingLow < bars().last().close)
    }

    @Test
    fun sizingRespectsRiskAndPositionCaps() {
        val plan = StructureRiskEngine.plan(
            entry = 100.0,
            atr = 2.0,
            sma20 = 97.0,
            swingLow = 96.5,
            nextResistance = 112.0,
            equity = 25_000.0,
            riskPctOfEquity = 0.01,
            maxPositionPct = 0.20
        )
        assertTrue(plan.shares > 0)
        assertTrue(plan.positionValue <= 5_000.0 + 0.01)
        assertTrue(plan.riskBudget == 250.0)
    }

    @Test
    fun nearbyRelevantResistanceCanInvalidateMinimumRewardRisk() {
        val plan = StructureRiskEngine.plan(
            entry = 100.0,
            atr = 2.0,
            sma20 = 97.0,
            swingLow = 96.0,
            nextResistance = 103.0
        )
        assertFalse(plan.valid)
        assertTrue("rr_below_min" in plan.reasons)
        assertTrue("target_capped_by_relevant_resistance" in plan.reasons)
    }

    @Test
    fun targetDefaultsToTwoPointFiveRWithoutResistance() {
        val plan = StructureRiskEngine.plan(
            entry = 100.0,
            atr = 2.0,
            sma20 = 97.0,
            swingLow = 96.0,
            nextResistance = null
        )
        assertEquals(2.5, plan.rr, 1e-9)
    }

    @Test
    fun ema20PullbackSelectsEma20InvalidationInsteadOfNearestGenericStop() {
        val plan = StructureRiskEngine.plan(
            entry = 100.0,
            atr = 2.0,
            sma20 = 98.5,
            sma50 = 95.0,
            swingLow = 96.0,
            support = 97.0,
            nextResistance = null,
            setupType = "PULLBACK_EMA20"
        )
        assertEquals("EMA20_STOP", plan.stopType)
        assertTrue(plan.stopCandidates.any { it.type == "ATR_STOP" })
        assertTrue(plan.stopCandidates.any { it.type == "SWING_LOW_STOP" })
        assertTrue(plan.stopCandidates.any { it.type == "SUPPORT_STOP" })
        assertTrue(plan.stopCandidates.any { it.type == "EMA50_STOP" })
    }

    @Test
    fun openingGapCreatesSeparateGapInvalidationCandidate() {
        val history = listOf(
            PriceBar(1L, 98.0, 100.0, 97.0, 99.0, 1_000_000L),
            PriceBar(2L, 101.0, 103.0, 100.0, 102.0, 1_000_000L)
        )
        val plan = StructureRiskEngine.plan(
            entry = 103.0,
            atr = 2.0,
            sma20 = 98.0,
            sma50 = 95.0,
            swingLow = 96.0,
            nextResistance = null,
            setupType = "BREAKOUT",
            bars = history
        )
        assertTrue(plan.stopCandidates.any { it.type == "GAP_INVALIDATION_STOP" })
    }
}
