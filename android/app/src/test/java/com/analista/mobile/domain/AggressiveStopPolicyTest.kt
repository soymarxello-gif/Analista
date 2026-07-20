package com.analista.mobile.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AggressiveStopPolicyTest {
    private fun input(
        stopAtr: Double = 0.8,
        rr: Double = 3.2,
        structure: Double = 85.0,
        setup: Double = 80.0,
        triggered: Boolean = true,
        quoteQuality: String = "HIGH",
        baseValid: Boolean = true
    ) = AggressiveStopPolicy.Input(
        baseRiskPlanValid = baseValid,
        stopAtrMultiple = stopAtr,
        riskReward = rr,
        structureScore = structure,
        setupQualityScore = setup,
        liveTriggerConfirmed = triggered,
        executionQuoteQuality = quoteQuality
    )

    @Test
    fun aggressiveStopRequiresEveryApprovedCondition() {
        val approved = AggressiveStopPolicy.evaluate(input())
        assertTrue(approved.valid)
        assertEquals("AGGRESSIVE_APPROVED", approved.status)

        listOf(
            input(rr = 2.99) to "aggressive_stop_requires_rr_3",
            input(structure = 79.9) to "aggressive_stop_requires_structure_80",
            input(setup = 74.9) to "aggressive_stop_requires_setup_75",
            input(triggered = false) to "aggressive_stop_requires_live_trigger",
            input(quoteQuality = "LOW") to "aggressive_stop_requires_confirmed_quote"
        ).forEach { (candidate, reason) ->
            val rejected = AggressiveStopPolicy.evaluate(candidate)
            assertFalse(rejected.valid)
            assertEquals("AGGRESSIVE_REJECTED", rejected.status)
            assertTrue(reason in rejected.reasons)
        }
    }

    @Test
    fun stopBelowHardMinimumIsRejected() {
        val result = AggressiveStopPolicy.evaluate(input(stopAtr = 0.59))
        assertFalse(result.valid)
        assertEquals("REJECT_TOO_TIGHT", result.status)
        assertTrue("stop_too_tight_below_0_6_atr" in result.reasons)
    }

    @Test
    fun preferredStopDoesNotRequireLiveTrigger() {
        val result = AggressiveStopPolicy.evaluate(input(stopAtr = 1.5, rr = 2.2, structure = 60.0, setup = 60.0, triggered = false))
        assertTrue(result.valid)
        assertEquals("PREFERRED", result.status)
    }

    @Test
    fun wideStopRemainsCautionNotAutomaticVeto() {
        val result = AggressiveStopPolicy.evaluate(input(stopAtr = 2.8, rr = 2.5))
        assertTrue(result.valid)
        assertEquals("WIDE_CAUTION", result.status)
        assertTrue("stop_too_wide_above_2_5_atr" in result.reasons)
    }
}
