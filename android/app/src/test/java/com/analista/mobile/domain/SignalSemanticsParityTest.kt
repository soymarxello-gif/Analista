package com.analista.mobile.domain

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SignalSemanticsParityTest {
    @Test
    fun androidFinalDecisionMatchesSharedSignalSemanticsFixture() {
        val resource = checkNotNull(javaClass.classLoader?.getResourceAsStream("signal_semantics_parity.json"))
        val root = JSONObject(resource.bufferedReader().use { it.readText() })
        assertEquals("signal-semantics-parity-1", root.getString("schemaVersion"))
        val cases = root.getJSONArray("cases")

        for (index in 0 until cases.length()) {
            val item = cases.getJSONObject(index)
            val name = item.getString("name")
            val price = item.getDouble("price")
            val marketCap = if (item.isNull("marketCap")) null else item.getLong("marketCap")
            val quoteType = if (item.isNull("quoteType")) null else item.getString("quoteType")
            val setupType = item.getString("setupType")
            val triggerConfirmed = item.getBoolean("triggerConfirmed")
            val failedBreakout = item.getBoolean("failedBreakout")
            val hardVetoReasons = TradingPolicy.hardVetoReasons(price, marketCap, quoteType)
            val preliminarySignal = when {
                hardVetoReasons.isNotEmpty() -> "VETO"
                setupType == "NO_VALID_SETUP" || failedBreakout -> "AVOID"
                triggerConfirmed -> "TRIGGER_CONFIRMED"
                else -> "READY_WAIT_TRIGGER"
            }
            val result = FinalDecisionEngine.decide(
                FinalDecisionEngine.Input(
                    preliminarySignal = preliminarySignal,
                    finalTradeScore = item.getDouble("finalTradeScore"),
                    setupType = setupType,
                    setupValid = setupType != "NO_VALID_SETUP",
                    macroRegime = "NEUTRAL",
                    macroConfidence = "HIGH",
                    fundamentalCoverage = "COMPLETE",
                    institutionalCoverage = "COMPLETE",
                    institutionalConflict = "NONE",
                    riskPlanValid = item.getBoolean("riskPlanValid"),
                    liveTriggerConfirmed = triggerConfirmed,
                    actionability = if (triggerConfirmed) "ACTIONABLE_REVIEW" else "WAIT_TRIGGER",
                    executionQuoteQuality = item.getString("executionQuoteQuality"),
                    executionFreshness = "FRESH",
                    executionSessionOpen = true,
                    eligibilityVerified = marketCap != null && !quoteType.isNullOrBlank(),
                    dataQualityAllowsExecution = item.getBoolean("dataQualityAllowsExecution"),
                    failedBreakout = failedBreakout,
                    hardVetoReasons = hardVetoReasons
                )
            )

            val expected = item.getString("expectedSignal")
            assertEquals(name, expected, result.finalSignal)
            if (expected in setOf("READY_WAIT_TRIGGER", "TRIGGER_CONFIRMED")) {
                assertTrue(name, result.eligibleForContract)
            } else {
                assertFalse(name, result.eligibleForContract)
            }
        }
    }
}
