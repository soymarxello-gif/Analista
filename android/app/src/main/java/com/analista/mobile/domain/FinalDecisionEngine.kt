package com.analista.mobile.domain

object FinalDecisionEngine {
    const val VERSION = "final-decision-3"

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

        if (input.preliminarySignal == "VETO") vetoReasons += "preliminary_veto"
        if (!input.setupValid || input.setupType == "NO_VALID_SETUP") vetoReasons += "no_valid_setup"

        val finalSignal = when {
            vetoReasons.isNotEmpty() -> "VETO"
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
            !input.dataQualityAllowsExecution -> {
                penalties += "data_quality_blocks_final_decision"
                "WATCHLIST"
            }
            input.executionQuoteQuality == "LOW" -> {
                penalties += "execution_quote_unconfirmed"
                "WATCHLIST"
            }
            input.executionFreshness in setOf("STALE", "UNKNOWN") -> {
                penalties += "execution_quote_not_fresh"
                "WATCHLIST"
            }
            input.institutionalConflict == "HIGH" -> {
                penalties += "institutional_conflict_high"
                "WATCHLIST"
            }
            input.finalTradeScore < thresholds.minimumReadyScore -> {
                penalties += "final_trade_score_below_ready_threshold"
                "WATCHLIST"
            }
            input.liveTriggerConfirmed && input.executionFreshness != "FRESH" -> {
                penalties += "live_trigger_requires_fresh_quote"
                "WATCHLIST"
            }
            input.liveTriggerConfirmed && input.actionability == "ACTIONABLE_REVIEW" &&
                input.finalTradeScore >= thresholds.minimumConfirmedScore -> "TRIGGER_CONFIRMED"
            input.liveTriggerConfirmed -> {
                penalties += "live_trigger_not_confirmable"
                "WATCHLIST"
            }
            else -> "READY_WAIT_TRIGGER"
        }

        val confidence = confidence(input)
        val eligible = finalSignal in setOf("READY_WAIT_TRIGGER", "TRIGGER_CONFIRMED") &&
            input.riskPlanValid &&
            input.dataQualityAllowsExecution &&
            input.executionQuoteQuality != "LOW" &&
            input.executionFreshness in setOf("FRESH", "DELAYED_ACCEPTABLE") &&
            !input.failedBreakout &&
            input.institutionalConflict != "HIGH" &&
            vetoReasons.isEmpty()

        require(finalSignal in TradingPolicy.allowedSignals)
        if (finalSignal == "TRIGGER_CONFIRMED") {
            require(input.liveTriggerConfirmed)
            require(input.actionability == "ACTIONABLE_REVIEW")
            require(input.executionFreshness == "FRESH")
            require(input.finalTradeScore >= thresholds.minimumConfirmedScore)
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
            !input.dataQualityAllowsExecution || input.executionQuoteQuality == "LOW" ||
                input.executionFreshness in setOf("STALE", "UNKNOWN") -> "LOW"
            input.executionFreshness == "DELAYED_ACCEPTABLE" -> "MEDIUM"
            coverage.any { it in setOf("UNKNOWN", "EMPTY", "ERROR", "UNAVAILABLE", "STALE") } -> "LOW"
            coverage.any { it in setOf("PARTIAL", "AVAILABLE_PARTIAL", "MEDIUM") } -> "MEDIUM"
            else -> "HIGH"
        }
    }
}