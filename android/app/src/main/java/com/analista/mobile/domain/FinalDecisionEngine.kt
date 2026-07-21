package com.analista.mobile.domain

object FinalDecisionEngine {
    const val VERSION = "final-decision-5"

    data class Thresholds(
        val minimumReadyScore: Double = 65.0,
        val minimumConfirmedScore: Double = 75.0
    )

    data class Input(
        val preliminarySignal: String,
        val finalTradeScore: Double,
        val setupType: String,
        val setupValid: Boolean,
        val macroRegime: String,
        val macroConfidence: String,
        val fundamentalCoverage: String,
        val institutionalCoverage: String,
        val institutionalConflict: String = "NONE",
        val riskPlanValid: Boolean,
        val liveTriggerConfirmed: Boolean,
        val actionability: String,
        val executionQuoteQuality: String,
        val executionFreshness: String = "UNKNOWN",
        val executionSessionOpen: Boolean = false,
        val eligibilityVerified: Boolean = true,
        val dataQualityAllowsExecution: Boolean,
        val failedBreakout: Boolean,
        val hardVetoReasons: List<String> = emptyList(),
        val penaltyReasons: List<String> = emptyList()
    )

    data class Decision(
        val preliminarySignal: String,
        val finalSignal: String,
        val finalTradeScore: Double,
        val eligibleForContract: Boolean,
        val confidence: String,
        val vetoReasons: List<String>,
        val penaltyReasons: List<String>,
        val decisionVersion: String = VERSION
    )

    fun decide(input: Input, thresholds: Thresholds = Thresholds()): Decision {
        require(input.preliminarySignal in TradingPolicy.allowedSignals)
        require(input.finalTradeScore in 0.0..100.0)
        require(input.executionFreshness in setOf("FRESH", "DELAYED_ACCEPTABLE", "STALE", "UNKNOWN"))
        require(thresholds.minimumReadyScore in 0.0..100.0)
        require(thresholds.minimumConfirmedScore in thresholds.minimumReadyScore..100.0)

        val vetoReasons = input.hardVetoReasons.toMutableList()
        val penalties = input.penaltyReasons.toMutableList()
        val riskOff = input.macroRegime.trim().uppercase() == "RISK_OFF"
        val readyThreshold = (thresholds.minimumReadyScore + if (riskOff) 5.0 else 0.0).coerceAtMost(100.0)
        val confirmedThreshold = (thresholds.minimumConfirmedScore + if (riskOff) 10.0 else 0.0).coerceAtMost(100.0)

        if (input.preliminarySignal == "VETO") vetoReasons += "preliminary_veto"
        if (riskOff) penalties += "risk_off_thresholds_elevated"

        val finalSignal = when {
            vetoReasons.isNotEmpty() -> "VETO"
            !input.setupValid || input.setupType == "NO_VALID_SETUP" -> {
                penalties += "no_valid_setup"
                "AVOID"
            }
            input.preliminarySignal == "AVOID" -> {
                penalties += "preliminary_avoid_not_promoted"
                "AVOID"
            }
            input.preliminarySignal == "WATCHLIST" -> {
                penalties += "preliminary_watchlist_not_promoted"
                "WATCHLIST"
            }
            input.failedBreakout -> {
                penalties += "failed_breakout"
                "AVOID"
            }
            !input.riskPlanValid -> {
                penalties += "risk_plan_invalid"
                "AVOID"
            }
            !input.eligibilityVerified -> {
                penalties += "eligibility_metadata_unverified"
                "WATCHLIST"
            }
            !input.dataQualityAllowsExecution -> {
                penalties += "data_quality_blocks_final_decision"
                "WATCHLIST"
            }
            !input.executionSessionOpen -> {
                penalties += "market_session_blocks_contract"
                "WATCHLIST"
            }
            input.executionQuoteQuality == "LOW" -> {
                penalties += "execution_quote_unconfirmed"
                "WATCHLIST"
            }
            input.executionFreshness in setOf("STALE", "UNKNOWN") -> {
                penalties += if (input.executionFreshness == "STALE") "quote_stale" else "quote_freshness_unknown"
                "WATCHLIST"
            }
            input.institutionalConflict == "HIGH" -> {
                penalties += "institutional_conflict_high"
                "WATCHLIST"
            }
            input.finalTradeScore < readyThreshold -> {
                penalties += "final_trade_score_below_ready_threshold"
                "WATCHLIST"
            }
            input.liveTriggerConfirmed && input.executionFreshness != "FRESH" -> {
                penalties += "quote_not_fresh_for_confirmation"
                "WATCHLIST"
            }
            input.liveTriggerConfirmed && input.actionability == "ACTIONABLE_REVIEW" &&
                input.finalTradeScore >= confirmedThreshold -> "TRIGGER_CONFIRMED"
            input.liveTriggerConfirmed -> {
                penalties += "live_trigger_not_confirmable"
                "WATCHLIST"
            }
            else -> "READY_WAIT_TRIGGER"
        }

        val confidence = confidence(input)
        val eligibleFreshness = when (finalSignal) {
            "TRIGGER_CONFIRMED" -> input.executionFreshness == "FRESH"
            "READY_WAIT_TRIGGER" -> input.executionFreshness in setOf("FRESH", "DELAYED_ACCEPTABLE")
            else -> false
        }
        val eligible = finalSignal in setOf("READY_WAIT_TRIGGER", "TRIGGER_CONFIRMED") &&
            input.riskPlanValid &&
            input.eligibilityVerified &&
            input.dataQualityAllowsExecution &&
            input.executionSessionOpen &&
            input.executionQuoteQuality != "LOW" &&
            eligibleFreshness &&
            !input.failedBreakout &&
            input.institutionalConflict != "HIGH" &&
            vetoReasons.isEmpty()

        require(finalSignal in TradingPolicy.allowedSignals)
        if (finalSignal == "TRIGGER_CONFIRMED") {
            require(input.liveTriggerConfirmed)
            require(input.actionability == "ACTIONABLE_REVIEW")
            require(input.executionFreshness == "FRESH")
            require(input.executionSessionOpen)
            require(input.finalTradeScore >= confirmedThreshold)
        }
        if (finalSignal == "READY_WAIT_TRIGGER") require(!input.liveTriggerConfirmed)

        return Decision(
            preliminarySignal = input.preliminarySignal,
            finalSignal = finalSignal,
            finalTradeScore = input.finalTradeScore,
            eligibleForContract = eligible,
            confidence = confidence,
            vetoReasons = vetoReasons.distinct(),
            penaltyReasons = penalties.distinct()
        )
    }

    private fun confidence(input: Input): String {
        val coverage = listOf(
            input.macroConfidence,
            input.fundamentalCoverage,
            input.institutionalCoverage
        ).map { it.trim().uppercase() }
        return when {
            !input.eligibilityVerified || !input.executionSessionOpen -> "LOW"
            !input.dataQualityAllowsExecution || input.executionQuoteQuality == "LOW" -> "LOW"
            input.executionFreshness in setOf("STALE", "UNKNOWN") -> "LOW"
            coverage.any { it in setOf("UNKNOWN", "EMPTY", "ERROR", "UNAVAILABLE", "STALE") } -> "LOW"
            input.executionFreshness == "DELAYED_ACCEPTABLE" -> "MEDIUM"
            coverage.any { it in setOf("PARTIAL", "AVAILABLE_PARTIAL", "MEDIUM", "LOW") } -> "MEDIUM"
            else -> "HIGH"
        }
    }
}
