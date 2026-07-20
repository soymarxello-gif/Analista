package com.analista.mobile.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class InstitutionalReleaseGateTest {
    private val hash = "a".repeat(64)

    private fun input(
        p0Violations: Int = 0,
        contractMismatches: Int = 0,
        triggerFreshnessViolations: Int = 0,
        institutionalConflictViolations: Int = 0,
        aggressiveStopViolations: Int = 0,
        replayStatus: String = "COMPLETE",
        replayMismatches: Int = 0,
        missingDatasets: Int = 0,
        reproducibilityStatus: String = "COMPLETE",
        configurationHash: String = hash,
        universeHash: String = hash,
        calendarVersion: String = "xnys-2025-2028-v1",
        rankingPromotionStatus: String = "KEEP_LEGACY_ORDER",
        signatureVerified: Boolean = true,
        manualReviewOnly: Boolean = true,
        buySetupActiveEnabled: Boolean = false,
        portfolioConstructionEnabled: Boolean = false
    ) = InstitutionalReleaseGate.Input(
        p0ViolationCount = p0Violations,
        contractDecisionMismatchCount = contractMismatches,
        triggerFreshnessViolationCount = triggerFreshnessViolations,
        institutionalConflictViolationCount = institutionalConflictViolations,
        aggressiveStopViolationCount = aggressiveStopViolations,
        replayStatus = replayStatus,
        replayMismatchCount = replayMismatches,
        missingDatasetCount = missingDatasets,
        reproducibilityStatus = reproducibilityStatus,
        configurationHash = configurationHash,
        universeHash = universeHash,
        calendarVersion = calendarVersion,
        rankingPromotionStatus = rankingPromotionStatus,
        apkSignatureVerified = signatureVerified,
        manualReviewOnly = manualReviewOnly,
        buySetupActiveEnabled = buySetupActiveEnabled,
        portfolioConstructionEnabled = portfolioConstructionEnabled
    )

    @Test
    fun completeAuditedBuildIsReadyForPhysicalAcceptance() {
        val result = InstitutionalReleaseGate.evaluate(input())

        assertEquals("READY_FOR_DEVICE_ACCEPTANCE", result.status)
        assertTrue(result.blockingReasons.isEmpty())
        assertTrue("legacy_ranking_retained_pending_predictive_evidence" in result.warnings)
    }

    @Test
    fun replayMismatchAndMissingDatasetBlockRelease() {
        val result = InstitutionalReleaseGate.evaluate(
            input(replayStatus = "MISMATCH", replayMismatches = 2, missingDatasets = 1)
        )

        assertEquals("BLOCKED", result.status)
        assertTrue("replay_not_complete" in result.blockingReasons)
        assertTrue("replay_mismatches_detected" in result.blockingReasons)
        assertTrue("replay_datasets_missing" in result.blockingReasons)
    }

    @Test
    fun executionAndRiskInvariantViolationsBlockRelease() {
        val result = InstitutionalReleaseGate.evaluate(
            input(
                contractMismatches = 1,
                triggerFreshnessViolations = 1,
                institutionalConflictViolations = 1,
                aggressiveStopViolations = 1
            )
        )

        assertEquals("BLOCKED", result.status)
        assertTrue("contracts_not_aligned_with_final_decisions" in result.blockingReasons)
        assertTrue("confirmed_triggers_without_fresh_quote" in result.blockingReasons)
        assertTrue("institutional_conflict_gate_breached" in result.blockingReasons)
        assertTrue("aggressive_stop_policy_breached" in result.blockingReasons)
    }

    @Test
    fun productSafetyContractCannotBeRelaxedForV3Release() {
        val result = InstitutionalReleaseGate.evaluate(
            input(
                manualReviewOnly = false,
                buySetupActiveEnabled = true,
                portfolioConstructionEnabled = true
            )
        )

        assertEquals("BLOCKED", result.status)
        assertTrue("manual_review_contract_disabled" in result.blockingReasons)
        assertTrue("buy_setup_active_must_remain_disabled" in result.blockingReasons)
        assertTrue("portfolio_construction_must_remain_disabled" in result.blockingReasons)
    }

    @Test
    fun invalidRunIdentityBlocksRelease() {
        val result = InstitutionalReleaseGate.evaluate(
            input(configurationHash = "bad", universeHash = "", calendarVersion = "UNKNOWN", signatureVerified = false)
        )

        assertEquals("BLOCKED", result.status)
        assertTrue("configuration_hash_invalid" in result.blockingReasons)
        assertTrue("universe_hash_invalid" in result.blockingReasons)
        assertTrue("calendar_version_missing" in result.blockingReasons)
        assertTrue("apk_signature_not_verified" in result.blockingReasons)
    }
}
