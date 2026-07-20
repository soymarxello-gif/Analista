package com.analista.mobile.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FinalDecisionEngineTest {
    private fun input(
        preliminarySignal: String = "READY_WAIT_TRIGGER",
        finalTradeScore: Double = 80.0,
        setupType: String = "BREAKOUT",
        setupValid: Boolean = true,
        macroRegime: String = "RISK_ON",
        macroConfidence: String = "HIGH",
        fundamentalCoverage: String = "COMPLETE",
        institutionalCoverage: String = "COMPLETE",
        institutionalConflict: String = "NONE",
        riskPlanValid: Boolean = true,
        liveTriggerConfirmed: Boolean = false,
        actionability: String = "WAIT_TRIGGER",
        executionQuoteQuality: String = "HIGH",
        executionFreshness: String = "FRESH",
        dataQualityAllowsExecution: Boolean = true,
        failedBreakout: Boolean = false,
        hardVetoReasons: List<String> = emptyList()
    ) = FinalDecisionEngine.Input(
        preliminarySignal = preliminarySignal,
        finalTradeScore = finalTradeScore,
        setupType = setupType,
        setupValid = setupValid,
        macroRegime = macroRegime,
        macroConfidence = macroConfidence,
        fundamentalCoverage = fundamentalCoverage,
        institutionalCoverage = institutionalCoverage,
        institutionalConflict = institutionalConflict,
        riskPlanValid = riskPlanValid,
        liveTriggerConfirmed = liveTriggerConfirmed,
        actionability = actionability,
        executionQuoteQuality = executionQuoteQuality,
        executionFreshness = executionFreshness,
        dataQualityAllowsExecution = dataQualityAllowsExecution,
        failedBreakout = failedBreakout,
        hardVetoReasons = hardVetoReasons
    )

    @Test
    fun hardVetoAlwaysWinsAfterAllOverlays() {
        val result = FinalDecisionEngine.decide(input(hardVetoReasons = listOf("market_cap_below_min")))
        assertEquals("VETO", result.finalSignal)
        assertFalse(result.eligibleForContract)
        assertTrue("market_cap_below_min" in result.vetoReasons)
    }

    @Test
    fun preliminaryAvoidCannotBePromotedByHighOverlayScore() {
        val result = FinalDecisionEngine.decide(input(preliminarySignal = "AVOID", finalTradeScore = 100.0))
        assertEquals("AVOID", result.finalSignal)
        assertFalse(result.eligibleForContract)
        assertTrue("preliminary_avoid_not_promoted" in result.penaltyReasons)
    }

    @Test
    fun preliminaryWatchlistCannotBePromotedByHighOverlayScore() {
        val result = FinalDecisionEngine.decide(input(preliminarySignal = "WATCHLIST", finalTradeScore = 100.0))
        assertEquals("WATCHLIST", result.finalSignal)
        assertFalse(result.eligibleForContract)
        assertTrue("preliminary_watchlist_not_promoted" in result.penaltyReasons)
    }

    @Test
    fun failedBreakoutIsAvoidEvenWithHighScore() {
        val result = FinalDecisionEngine.decide(input(finalTradeScore = 95.0, failedBreakout = true))
        assertEquals("AVOID", result.finalSignal)
        assertFalse(result.eligibleForContract)
        assertTrue("failed_breakout" in result.penaltyReasons)
    }

    @Test
    fun institutionalConflictCanBlockTechnicalSignal() {
        val result = FinalDecisionEngine.decide(
            input(preliminarySignal = "TRIGGER_CONFIRMED", liveTriggerConfirmed = true,
                actionability = "ACTIONABLE_REVIEW", institutionalConflict = "HIGH")
        )
        assertEquals("WATCHLIST", result.finalSignal)
        assertFalse(result.eligibleForContract)
        assertTrue("institutional_conflict_high" in result.penaltyReasons)
    }

    @Test
    fun validUntriggeredSetupBecomesReadyWaitTrigger() {
        val result = FinalDecisionEngine.decide(input(liveTriggerConfirmed = false))
        assertEquals("READY_WAIT_TRIGGER", result.finalSignal)
        assertTrue(result.eligibleForContract)
    }

    @Test
    fun confirmedSignalRequiresFreshLiveTriggerAndActionableExecution() {
        val result = FinalDecisionEngine.decide(
            input(
                preliminarySignal = "TRIGGER_CONFIRMED",
                liveTriggerConfirmed = true,
                actionability = "ACTIONABLE_REVIEW",
                finalTradeScore = 80.0
            )
        )
        assertEquals("TRIGGER_CONFIRMED", result.finalSignal)
        assertTrue(result.eligibleForContract)
    }

    @Test
    fun delayedQuoteCanWaitButCannotConfirm() {
        val waiting = FinalDecisionEngine.decide(input(executionFreshness = "DELAYED_ACCEPTABLE"))
        assertEquals("READY_WAIT_TRIGGER", waiting.finalSignal)
        assertTrue(waiting.eligibleForContract)
        assertEquals("MEDIUM", waiting.confidence)

        val triggered = FinalDecisionEngine.decide(
            input(
                preliminarySignal = "TRIGGER_CONFIRMED",
                liveTriggerConfirmed = true,
                actionability = "ACTIONABLE_REVIEW",
                executionFreshness = "DELAYED_ACCEPTABLE"
            )
        )
        assertEquals("WATCHLIST", triggered.finalSignal)
        assertFalse(triggered.eligibleForContract)
    }

    @Test
    fun staleOrUnknownQuoteBlocksEveryContract() {
        listOf("STALE", "UNKNOWN").forEach { freshness ->
            val result = FinalDecisionEngine.decide(input(executionFreshness = freshness))
            assertEquals("WATCHLIST", result.finalSignal)
            assertFalse(result.eligibleForContract)
            assertEquals("LOW", result.confidence)
        }
    }

    @Test
    fun lowQuoteQualityBlocksContract() {
        val result = FinalDecisionEngine.decide(
            input(liveTriggerConfirmed = true, actionability = "ACTIONABLE_REVIEW", executionQuoteQuality = "LOW")
        )
        assertEquals("WATCHLIST", result.finalSignal)
        assertFalse(result.eligibleForContract)
        assertEquals("LOW", result.confidence)
    }

    @Test
    fun liveTriggerBelowConfirmedScoreDoesNotMasqueradeAsWaiting() {
        val result = FinalDecisionEngine.decide(
            input(liveTriggerConfirmed = true, actionability = "ACTIONABLE_REVIEW", finalTradeScore = 70.0)
        )
        assertEquals("WATCHLIST", result.finalSignal)
        assertFalse(result.eligibleForContract)
        assertTrue("live_trigger_not_confirmable" in result.penaltyReasons)
    }

    @Test
    fun unknownInstitutionalCoverageReducesConfidenceWithoutInventingNeutrality() {
        val result = FinalDecisionEngine.decide(input(institutionalCoverage = "UNKNOWN"))
        assertEquals("LOW", result.confidence)
        assertEquals("READY_WAIT_TRIGGER", result.finalSignal)
    }
}
