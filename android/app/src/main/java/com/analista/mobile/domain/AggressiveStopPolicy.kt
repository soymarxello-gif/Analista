package com.analista.mobile.domain

object AggressiveStopPolicy {
    const val VERSION = "aggressive-stop-policy-1"

    data class Input(
        val baseRiskPlanValid: Boolean,
        val stopAtrMultiple: Double,
        val riskReward: Double,
        val structureScore: Double,
        val setupQualityScore: Double,
        val liveTriggerConfirmed: Boolean,
        val executionQuoteQuality: String
    )

    data class Result(
        val valid: Boolean,
        val status: String,
        val reasons: List<String>
    )

    fun evaluate(input: Input): Result {
        require(input.stopAtrMultiple >= 0.0)
        require(input.riskReward.isFinite())
        require(input.structureScore in 0.0..100.0)
        require(input.setupQualityScore in 0.0..100.0)

        val reasons = mutableListOf<String>()
        if (!input.baseRiskPlanValid) reasons += "base_risk_plan_invalid"
        if (input.stopAtrMultiple < 0.60) reasons += "stop_too_tight_below_0_6_atr"
        if (input.stopAtrMultiple > 2.50) reasons += "stop_too_wide_above_2_5_atr"

        val aggressive = input.stopAtrMultiple in 0.60..<1.0
        if (aggressive) {
            if (input.riskReward < 3.0) reasons += "aggressive_stop_requires_rr_3"
            if (input.structureScore < 80.0) reasons += "aggressive_stop_requires_structure_80"
            if (input.setupQualityScore < 75.0) reasons += "aggressive_stop_requires_setup_75"
            if (!input.liveTriggerConfirmed) reasons += "aggressive_stop_requires_live_trigger"
            if (input.executionQuoteQuality == "LOW") reasons += "aggressive_stop_requires_confirmed_quote"
        }

        val valid = input.baseRiskPlanValid &&
            input.stopAtrMultiple >= 0.60 &&
            if (aggressive) {
                input.riskReward >= 3.0 &&
                    input.structureScore >= 80.0 &&
                    input.setupQualityScore >= 75.0 &&
                    input.liveTriggerConfirmed &&
                    input.executionQuoteQuality != "LOW"
            } else true

        val status = when {
            input.stopAtrMultiple < 0.60 -> "REJECT_TOO_TIGHT"
            aggressive && valid -> "AGGRESSIVE_APPROVED"
            aggressive -> "AGGRESSIVE_REJECTED"
            input.stopAtrMultiple > 2.50 -> "WIDE_CAUTION"
            valid -> "PREFERRED"
            else -> "INVALID"
        }
        return Result(valid = valid, status = status, reasons = reasons.distinct())
    }
}
