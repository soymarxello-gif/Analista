package com.analista.mobile.domain

import org.junit.Assert.assertTrue
import org.junit.Test

class RollingWalkForwardEngineTest {
    @Test
    fun createsMultipleEmbargoedFoldsAndUsesOosGate() {
        val observations = (1L..500L).map { index ->
            WalkForwardStatisticsEngine.Observation(
                observationId = "obs-$index",
                decisionTimestampUtc = index,
                setupType = if (index % 2L == 0L) "BREAKOUT" else "PULLBACK",
                macroRegime = if (index % 3L == 0L) "RISK_OFF" else "RISK_ON",
                activated = true,
                tradeReturnR = 0.5,
                mfePct = 2.0,
                maePct = -1.0,
                holdingSessions = 5,
                status = "CLOSED_TARGET"
            )
        }
        val report = RollingWalkForwardEngine.evaluate(
            observations,
            RollingWalkForwardEngine.Config(
                minimumTraining = 100,
                validationSize = 40,
                testSize = 40,
                stepSize = 40,
                embargoObservations = 21,
                minimumOutOfSampleClosed = 200,
                bootstrapSamples = 200
            )
        )
        assertTrue(report.folds.size > 1)
        assertTrue(report.outOfSampleClosed >= 200)
        assertTrue(report.expectancyCi95!!.first > 0.0)
        assertTrue(report.eligibleForPromotion)
    }
}
