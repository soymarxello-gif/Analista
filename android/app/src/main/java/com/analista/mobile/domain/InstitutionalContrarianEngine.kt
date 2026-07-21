package com.analista.mobile.domain

object InstitutionalContrarianEngine {
    const val VERSION = "institutional-contrarian-3"

    data class Component(
        val score: Double?,
        val status: String,
        val reasons: List<String> = emptyList()
    )

    data class Input(
        val options: OptionMetricsEngine.Assessment?,
        val volumeAccumulation: Component,
        val insiders: Component,
        val futuresPositioning: Component,
        val bullishConsensusPercentile: Double? = null,
        val priceTrendConstructive: Boolean,
        val technicalScore: Double,
        val optionsComponent: Component? = null,
        val optionsBiasOverride: String? = null,
        val marketOptionsRegime: String = "UNKNOWN",
        val marketOptionsAdjustment: Double = 0.0
    )

    data class Assessment(
        val optionsScore: Double?,
        val volumeAccumulationScore: Double?,
        val insiderScore: Double?,
        val futuresPositioningScore: Double?,
        val institutionalCompositeScore: Double,
        val contrarianAdjustment: Double,
        val adjustedInstitutionalScore: Double,
        val coveragePct: Double,
        val coverageStatus: String,
        val conflict: String,
        val optionsBias: String,
        val reasons: List<String>,
        val engineVersion: String = VERSION
    )

    fun assess(input: Input): Assessment {
        require(input.technicalScore in 0.0..100.0)
        input.bullishConsensusPercentile?.let { require(it in 0.0..100.0) }
        require(input.marketOptionsAdjustment in -10.0..10.0)
        val optionScore = input.options?.score ?: input.optionsComponent?.score
        val components = listOf(
            Triple("options", optionScore, 0.50),
            Triple("volume", input.volumeAccumulation.score, 0.25),
            Triple("insiders", input.insiders.score, 0.15),
            Triple("futures", input.futuresPositioning.score, 0.10)
        )
        val available = components.filter { (_, score, _) -> score != null }
        val availableWeight = available.sumOf { it.third }
        val composite = if (availableWeight > 0.0) {
            available.sumOf { (_, score, weight) -> score!! * weight } / availableWeight
        } else 50.0
        val coveragePct = availableWeight * 100.0
        val optionsBias = input.options?.bias ?: input.optionsBiasOverride ?: "UNKNOWN_OPTIONS_FLOW"
        val reasons = mutableListOf<String>()
        reasons += input.options?.reasons.orEmpty()
        reasons += input.optionsComponent?.reasons.orEmpty()
        reasons += input.volumeAccumulation.reasons
        reasons += input.insiders.reasons
        reasons += input.futuresPositioning.reasons
        if (availableWeight < 1.0) reasons += "institutional_coverage_incomplete"
        if (optionScore == null || optionsBias == "UNKNOWN_OPTIONS_FLOW") reasons += "options_unknown_not_neutral"

        var contrarian = input.marketOptionsAdjustment
        when (input.marketOptionsRegime) {
            "CROWDED_BULLISH" -> reasons += "market_options_crowded_bullish_penalty"
            "CROWDED_BEARISH" -> reasons += "market_options_crowded_bearish_context"
            "UNKNOWN" -> reasons += "market_options_context_unknown"
        }
        when {
            optionsBias == "CROWDED_BULLISH" -> {
                contrarian -= 10.0
                reasons += "contrarian_crowded_bullish_penalty"
            }
            optionsBias == "CROWDED_BEARISH" && input.priceTrendConstructive -> {
                contrarian += 4.0
                reasons += "contrarian_crowded_bearish_support"
            }
        }
        input.bullishConsensusPercentile?.let { percentile ->
            when {
                percentile >= 90.0 && input.technicalScore >= 70.0 -> {
                    contrarian -= 8.0
                    reasons += "consensus_extreme_bullish"
                }
                percentile <= 10.0 && input.priceTrendConstructive -> {
                    contrarian += 5.0
                    reasons += "consensus_extreme_bearish"
                }
            }
        }
        contrarian = contrarian.coerceIn(-15.0, 10.0)
        val adjusted = (composite + contrarian).coerceIn(0.0, 100.0)
        val adverseOptions = optionsBias in setOf("BEARISH_WITH_DATA", "CROWDED_BEARISH")
        val volumeDistribution = input.volumeAccumulation.score?.let { it < 35.0 } == true
        val futuresAdverse = input.futuresPositioning.score?.let { it <= 35.0 } == true &&
            input.futuresPositioning.status in setOf("COMPLETE", "AVAILABLE_COMPLETE")
        val conflict = when {
            coveragePct >= 70.0 && optionsBias == "CROWDED_BEARISH" && adjusted <= 50.0 -> "HIGH"
            coveragePct >= 70.0 && adverseOptions && adjusted <= 42.0 -> "HIGH"
            coveragePct >= 70.0 && adverseOptions && volumeDistribution -> "HIGH"
            coveragePct >= 70.0 && futuresAdverse && volumeDistribution -> "HIGH"
            adverseOptions || volumeDistribution || futuresAdverse -> "MEDIUM"
            else -> "NONE"
        }
        if (conflict == "HIGH") reasons += "institutional_conflict_high"
        val coverageStatus = when {
            coveragePct >= 85.0 -> "COMPLETE"
            coveragePct >= 40.0 -> "PARTIAL"
            else -> "UNKNOWN"
        }
        return Assessment(
            optionsScore = optionScore,
            volumeAccumulationScore = input.volumeAccumulation.score,
            insiderScore = input.insiders.score,
            futuresPositioningScore = input.futuresPositioning.score,
            institutionalCompositeScore = round2(composite),
            contrarianAdjustment = round2(contrarian),
            adjustedInstitutionalScore = round2(adjusted),
            coveragePct = round2(coveragePct),
            coverageStatus = coverageStatus,
            conflict = conflict,
            optionsBias = optionsBias,
            reasons = reasons.distinct()
        )
    }

    private fun round2(value: Double) = kotlin.math.round(value * 100.0) / 100.0
}
