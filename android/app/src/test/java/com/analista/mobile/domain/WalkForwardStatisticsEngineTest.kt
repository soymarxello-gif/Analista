package com.analista.mobile.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WalkForwardStatisticsEngineTest {
    @Test
    fun partitionsStrictlyByDecisionTimeWithoutLeakage() {
        val rows = (1L..10L).reversed().map { observation(it, returnR = 1.0) }
        val result = WalkForwardStatisticsEngine.evaluate(
            rows,
            partitionConfig = WalkForwardStatisticsEngine.PartitionConfig(trainingPct = 0.5, validationPct = 0.2),
            thresholds = permissiveThresholds()
        )
        assertEquals(1L, result.training.firstTimestampUtc)
        assertEquals(5L, result.training.lastTimestampUtc)
        assertEquals(6L, result.validation.firstTimestampUtc)
        assertEquals(7L, result.validation.lastTimestampUtc)
        assertEquals(8L, result.test.firstTimestampUtc)
        assertEquals(10L, result.test.lastTimestampUtc)
    }

    @Test
    fun calculatesExpectancyHitRateProfitFactorAndDrawdown() {
        val returns = listOf(1.0, -0.5, 2.0, -1.0)
        val result = WalkForwardStatisticsEngine.evaluate(
            returns.mapIndexed { index, value -> observation(index + 1L, returnR = value) },
            partitionConfig = WalkForwardStatisticsEngine.PartitionConfig(trainingPct = 0.0, validationPct = 0.0),
            thresholds = permissiveThresholds(minimumClosed = 4)
        )
        val metrics = result.test.metrics
        assertEquals(0.375, metrics.expectancyR!!, 0.0001)
        assertEquals(50.0, metrics.hitRatePct!!, 0.0001)
        assertEquals(2.0, metrics.profitFactor!!, 0.0001)
        assertEquals(1.0, metrics.maximumDrawdownR!!, 0.0001)
    }

    @Test
    fun defaultPromotionGatePassesOnlyWithEnoughOutOfSampleBreadth() {
        val rows = (1L..500L).map { index ->
            observation(
                index = index,
                setup = if (index % 2L == 0L) "BREAKOUT" else "PULLBACK_EMA20",
                regime = if (index % 4L < 2L) "RISK_ON" else "RISK_OFF",
                returnR = if (index % 3L == 0L) -0.5 else 1.0
            )
        }
        val result = WalkForwardStatisticsEngine.evaluate(rows)
        assertEquals(100, result.test.metrics.closedWithReturn)
        assertTrue(result.eligibleForRankingPromotion)
        assertTrue(result.reasons.isEmpty())
    }

    @Test
    fun insufficientOutOfSampleHistoryKeepsRankingInShadow() {
        val rows = (1L..100L).map { observation(it, returnR = 1.0) }
        val result = WalkForwardStatisticsEngine.evaluate(rows)
        assertFalse(result.eligibleForRankingPromotion)
        assertTrue("insufficient_out_of_sample_closed" in result.reasons)
    }

    @Test
    fun p0RegressionBlocksPromotionEvenWithLargeSample() {
        val rows = (1L..500L).map { index ->
            observation(
                index = index,
                setup = if (index % 2L == 0L) "BREAKOUT" else "PULLBACK_EMA20",
                regime = if (index % 4L < 2L) "RISK_ON" else "RISK_OFF",
                returnR = 1.0,
                p0Valid = index != 450L
            )
        }
        val result = WalkForwardStatisticsEngine.evaluate(rows)
        assertFalse(result.eligibleForRankingPromotion)
        assertTrue("p0_regression_present" in result.reasons)
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsDuplicateObservationIds() {
        WalkForwardStatisticsEngine.evaluate(
            listOf(observation(1L, returnR = 1.0), observation(1L, returnR = -1.0))
        )
    }

    private fun observation(
        index: Long,
        setup: String = "BREAKOUT",
        regime: String = "RISK_ON",
        returnR: Double?,
        p0Valid: Boolean = true
    ) = WalkForwardStatisticsEngine.Observation(
        observationId = "obs-$index",
        decisionTimestampUtc = index,
        setupType = setup,
        macroRegime = regime,
        sector = if (index % 2L == 0L) "TECH" else "INDUSTRIAL",
        activated = true,
        tradeReturnR = returnR,
        mfePct = 3.0,
        maePct = -1.0,
        holdingSessions = 5,
        status = "CLOSED_TARGET",
        p0Valid = p0Valid
    )

    private fun permissiveThresholds(minimumClosed: Int = 1) = WalkForwardStatisticsEngine.Thresholds(
        minimumOutOfSampleClosed = minimumClosed,
        minimumDominantSetupClosed = 1,
        dominantSetupMinSharePct = 0.0,
        minimumDistinctRegimes = 1
    )
}
