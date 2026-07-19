package com.analista.mobile.domain

import com.analista.mobile.data.ScanCandidate

/**
 * Stable audit projection used by V3 regression fixtures.
 * It records observable engine behavior without coupling tests to Room or Compose.
 */
data class EngineBehaviorSnapshot(
    val ticker: String,
    val preliminarySignal: String,
    val finalSignal: String?,
    val preliminaryScore: Double,
    val finalTradeScore: Double?,
    val plannedTrigger: Double?,
    val actionability: String,
    val vetoReasons: List<String>,
    val penaltyReasons: List<String>
) {
    companion object {
        fun from(
            candidate: ScanCandidate,
            finalSignal: String? = null,
            finalTradeScore: Double? = null
        ): EngineBehaviorSnapshot = EngineBehaviorSnapshot(
            ticker = candidate.ticker.trim().uppercase(),
            preliminarySignal = candidate.signal,
            finalSignal = finalSignal,
            preliminaryScore = candidate.score,
            finalTradeScore = finalTradeScore,
            plannedTrigger = candidate.plannedTrigger,
            actionability = candidate.actionabilityAtExecution,
            vetoReasons = candidate.allVetoReasons.distinct(),
            penaltyReasons = candidate.penaltyReasons.distinct()
        )
    }
}