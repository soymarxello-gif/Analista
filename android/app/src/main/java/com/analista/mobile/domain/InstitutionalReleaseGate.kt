package com.analista.mobile.domain

object InstitutionalReleaseGate {
    const val VERSION = "institutional-release-gate-1"

    data class Input(
        val p0ViolationCount: Int,
        val contractDecisionMismatchCount: Int,
        val triggerFreshnessViolationCount: Int,
        val institutionalConflictViolationCount: Int,
        val aggressiveStopViolationCount: Int,
        val replayStatus: String,
        val replayMismatchCount: Int,
        val missingDatasetCount: Int,
        val reproducibilityStatus: String,
        val configurationHash: String,
        val universeHash: String,
        val calendarVersion: String,
        val rankingPromotionStatus: String,
        val apkSignatureVerified: Boolean,
        val manualReviewOnly: Boolean = true,
        val buySetupActiveEnabled: Boolean = false,
        val portfolioConstructionEnabled: Boolean = false
    )

    data class Result(
        val status: String,
        val blockingReasons: List<String>,
        val warnings: List<String>,
        val gateVersion: String = VERSION
    )

    fun evaluate(input: Input): Result {
        require(
            listOf(
                input.p0ViolationCount,
                input.contractDecisionMismatchCount,
                input.triggerFreshnessViolationCount,
                input.institutionalConflictViolationCount,
                input.aggressiveStopViolationCount,
                input.replayMismatchCount,
                input.missingDatasetCount
            ).all { it >= 0 }
        ) { "violation counts must be non-negative" }

        val blocking = mutableListOf<String>()
        val warnings = mutableListOf<String>()

        if (input.p0ViolationCount > 0) blocking += "p0_invariants_failed"
        if (input.contractDecisionMismatchCount > 0) blocking += "contracts_not_aligned_with_final_decisions"
        if (input.triggerFreshnessViolationCount > 0) blocking += "confirmed_triggers_without_fresh_quote"
        if (input.institutionalConflictViolationCount > 0) blocking += "institutional_conflict_gate_breached"
        if (input.aggressiveStopViolationCount > 0) blocking += "aggressive_stop_policy_breached"

        val replayStatus = normalized(input.replayStatus)
        if (replayStatus != "COMPLETE") blocking += "replay_not_complete"
        if (input.replayMismatchCount > 0) blocking += "replay_mismatches_detected"
        if (input.missingDatasetCount > 0) blocking += "replay_datasets_missing"

        if (normalized(input.reproducibilityStatus) != "COMPLETE") {
            blocking += "reproducibility_not_complete"
        }
        if (!isSha256(input.configurationHash)) blocking += "configuration_hash_invalid"
        if (!isSha256(input.universeHash)) blocking += "universe_hash_invalid"
        if (normalized(input.calendarVersion) in setOf("", "UNKNOWN")) blocking += "calendar_version_missing"
        if (!input.apkSignatureVerified) blocking += "apk_signature_not_verified"

        if (!input.manualReviewOnly) blocking += "manual_review_contract_disabled"
        if (input.buySetupActiveEnabled) blocking += "buy_setup_active_must_remain_disabled"
        if (input.portfolioConstructionEnabled) blocking += "portfolio_construction_must_remain_disabled"

        when (normalized(input.rankingPromotionStatus)) {
            "PROMOTE_PROPOSED_RANKING" -> Unit
            "KEEP_LEGACY_ORDER" -> warnings += "legacy_ranking_retained_pending_predictive_evidence"
            else -> warnings += "ranking_promotion_status_unknown"
        }

        return Result(
            status = if (blocking.isEmpty()) "READY_FOR_DEVICE_ACCEPTANCE" else "BLOCKED",
            blockingReasons = blocking.distinct(),
            warnings = warnings.distinct()
        )
    }

    private fun normalized(value: String): String = value.trim().uppercase()
    private fun isSha256(value: String): Boolean = value.length == 64 && value.all { it in "0123456789abcdefABCDEF" }
}
