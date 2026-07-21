package com.analista.mobile.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class EngineBehaviorSnapshotTest {
    @Test
    fun fixtureCatalogCoversEveryApprovedRegressionScenario() {
        assertEquals(11, V3BehaviorFixtures.requiredScenarios.size)
        assertTrue("lost_breakout" in V3BehaviorFixtures.requiredScenarios)
        assertTrue("ambiguous_same_bar_exit" in V3BehaviorFixtures.requiredScenarios)
    }

    @Test
    fun snapshotCapturesCurrentPreliminaryBehaviorWithoutInventingFinalDecision() {
        val bars = V3BehaviorFixtures.trendingBars()
        val price = bars.last().close
        val candidate = TechnicalEngine.analyze(
            ticker = "test",
            bars = bars,
            context = V3BehaviorFixtures.context(V3BehaviorFixtures.validQuote(price))
        )

        val snapshot = EngineBehaviorSnapshot.from(candidate)

        assertEquals("TEST", snapshot.ticker)
        assertEquals(candidate.signal, snapshot.preliminarySignal)
        assertEquals(candidate.score, snapshot.preliminaryScore, 0.0)
        assertEquals(candidate.plannedTrigger, snapshot.plannedTrigger)
        assertEquals(candidate.actionabilityAtExecution, snapshot.actionability)
        assertNull(snapshot.finalSignal)
        assertNull(snapshot.finalTradeScore)
    }

    @Test
    fun snapshotPreservesNoSetupAsPenaltyInsteadOfUniverseVeto() {
        val bars = V3BehaviorFixtures.trendingBars()
        val price = bars.last().close
        val candidate = TechnicalEngine.analyze(
            ticker = "TEST",
            bars = bars,
            context = V3BehaviorFixtures.context(
                V3BehaviorFixtures.invalidQuote(price),
                setupType = "NO_VALID_SETUP"
            )
        )

        val snapshot = EngineBehaviorSnapshot.from(candidate)

        assertEquals("AVOID", snapshot.preliminarySignal)
        assertTrue(snapshot.vetoReasons.isEmpty())
        assertTrue("no_valid_setup" in snapshot.penaltyReasons)
        assertEquals(snapshot.vetoReasons.distinct(), snapshot.vetoReasons)
        assertEquals(snapshot.penaltyReasons.distinct(), snapshot.penaltyReasons)
    }
}
