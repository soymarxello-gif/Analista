package com.analista.mobile.domain

import kotlin.math.abs

object RankingPromotionEngine {
    const val VERSION = "ranking-promotion-1"

    data class Observation(
        val runId: String,
        val ticker: String,
        val decisionTimestampUtc: Long,
        val legacyRank: Int,
        val proposedRank: Int,
        val finalSignal: String,
        val eligibleForContract: Boolean,
        val p0Valid: Boolean,
        val macroRegime: String,
        val tradeReturnR: Double?,
        val mfePct: Double?,
        val maePct: Double?
    )

    data class Thresholds(
        val topK: Int = 5,
        val minimumClosedPerRanking: Int = 100,
        val minimumExpectancyImprovementR: Double = 0.10,
        val maximumDrawdownDeteriorationPct: Double = 10.0,
        val maximumMfeDeteriorationPctPoints: Double = 0.25,
        val maximumMaeDeteriorationPct: Double = 10.0,
        val minimumDistinctRegimes: Int = 2
    )

    data class Metrics(
        val selected: Int,
        val closed: Int,
        val expectancyR: Double?,
        val hitRatePct: Double?,
        val maximumDrawdownR: Double?,
        val averageMfePct: Double?,
        val averageMaePct: Double?,
        val invalidSelections: Int
    )

    data class Summary(
        val legacy: Metrics,
        val proposed: Metrics,
        val expectancyImprovementR: Double?,
        val drawdownDeteriorationPct: Double?,
        val mfeChangePctPoints: Double?,
        val maeDeteriorationPct: Double?,
        val distinctProposedRegimes: Int,
        val status: String,
        val reasons: List<String>,
        val engineVersion: String = VERSION
    )

    fun evaluate(
        observations: List<Observation>,
        walkForwardGatePassed: Boolean,
        thresholds: Thresholds = Thresholds()
    ): Summary {
        require(thresholds.topK > 0)
        require(thresholds.minimumClosedPerRanking > 0)
        require(thresholds.minimumDistinctRegimes > 0)
        require(observations.all {
            it.runId.isNotBlank() && it.ticker.isNotBlank() && it.decisionTimestampUtc > 0L &&
                it.legacyRank > 0 && it.proposedRank > 0 &&
                (it.tradeReturnR == null || it.tradeReturnR.isFinite())
        })
        require(observations.map { normalized(it.runId) to normalized(it.ticker) }.distinct().size == observations.size) {
            "ticker must be unique inside each run"
        }
        observations.groupBy { normalized(it.runId) }.values.forEach { runRows ->
            require(runRows.map { it.legacyRank }.distinct().size == runRows.size) { "legacy ranks must be unique per run" }
            require(runRows.map { it.proposedRank }.distinct().size == runRows.size) { "proposed ranks must be unique per run" }
        }

        val legacyRows = select(observations, thresholds.topK) { it.legacyRank }
        val proposedRows = select(observations, thresholds.topK) { it.proposedRank }
        val legacy = metrics(legacyRows)
        val proposed = metrics(proposedRows)
        val expectancyImprovement = pairedDifference(proposed.expectancyR, legacy.expectancyR)
        val drawdownDeterioration = relativeDeterioration(proposed.maximumDrawdownR, legacy.maximumDrawdownR)
        val mfeChange = pairedDifference(proposed.averageMfePct, legacy.averageMfePct)
        val maeDeterioration = maeDeterioration(proposed.averageMaePct, legacy.averageMaePct)
        val distinctRegimes = proposedRows
            .filter { it.tradeReturnR != null }
            .map { normalized(it.macroRegime) }
            .filter { it != "UNKNOWN" }
            .distinct()
            .size

        val reasons = mutableListOf<String>()
        if (!walkForwardGatePassed) reasons += "walk_forward_gate_failed"
        if (legacy.closed < thresholds.minimumClosedPerRanking) reasons += "insufficient_legacy_closed_sample"
        if (proposed.closed < thresholds.minimumClosedPerRanking) reasons += "insufficient_proposed_closed_sample"
        if (proposed.invalidSelections > 0) reasons += "proposed_ranking_selects_invalid_candidates"
        if (expectancyImprovement == null || expectancyImprovement < thresholds.minimumExpectancyImprovementR) {
            reasons += "expectancy_improvement_below_threshold"
        }
        if (drawdownDeterioration == null || drawdownDeterioration > thresholds.maximumDrawdownDeteriorationPct) {
            reasons += "drawdown_deterioration_above_threshold"
        }
        if (mfeChange == null || mfeChange < -thresholds.maximumMfeDeteriorationPctPoints) {
            reasons += "mfe_deterioration_above_threshold"
        }
        if (maeDeterioration == null || maeDeterioration > thresholds.maximumMaeDeteriorationPct) {
            reasons += "mae_deterioration_above_threshold"
        }
        if (distinctRegimes < thresholds.minimumDistinctRegimes) reasons += "insufficient_proposed_regime_breadth"

        return Summary(
            legacy = legacy,
            proposed = proposed,
            expectancyImprovementR = expectancyImprovement,
            drawdownDeteriorationPct = drawdownDeterioration,
            mfeChangePctPoints = mfeChange,
            maeDeteriorationPct = maeDeterioration,
            distinctProposedRegimes = distinctRegimes,
            status = if (reasons.isEmpty()) "PROMOTE_PROPOSED_RANKING" else "KEEP_LEGACY_ORDER",
            reasons = reasons.distinct()
        )
    }

    private fun select(
        observations: List<Observation>,
        topK: Int,
        rank: (Observation) -> Int
    ): List<Observation> = observations
        .groupBy { normalized(it.runId) }
        .values
        .flatMap { rows -> rows.sortedBy(rank).take(topK) }
        .sortedWith(compareBy<Observation> { it.decisionTimestampUtc }.thenBy { it.runId }.thenBy(rank))

    private fun metrics(rows: List<Observation>): Metrics {
        val closedRows = rows.filter { it.tradeReturnR != null }
        val returns = closedRows.map { it.tradeReturnR!! }
        var cumulative = 0.0
        var peak = 0.0
        var maxDrawdown = 0.0
        returns.forEach { value ->
            cumulative += value
            peak = maxOf(peak, cumulative)
            maxDrawdown = maxOf(maxDrawdown, peak - cumulative)
        }
        return Metrics(
            selected = rows.size,
            closed = closedRows.size,
            expectancyR = returns.averageOrNull(),
            hitRatePct = returns.takeIf { it.isNotEmpty() }?.let { values ->
                values.count { it > 0.0 } * 100.0 / values.size
            },
            maximumDrawdownR = returns.takeIf { it.isNotEmpty() }?.let { maxDrawdown },
            averageMfePct = closedRows.mapNotNull { it.mfePct }.averageOrNull(),
            averageMaePct = closedRows.mapNotNull { it.maePct }.averageOrNull(),
            invalidSelections = rows.count {
                !it.eligibleForContract || !it.p0Valid || it.finalSignal in setOf("VETO", "AVOID")
            }
        )
    }

    private fun pairedDifference(first: Double?, second: Double?): Double? =
        if (first != null && second != null) first - second else null

    private fun relativeDeterioration(proposed: Double?, legacy: Double?): Double? {
        if (proposed == null || legacy == null) return null
        if (legacy == 0.0) return if (proposed == 0.0) 0.0 else Double.POSITIVE_INFINITY
        return (proposed / legacy - 1.0) * 100.0
    }

    private fun maeDeterioration(proposed: Double?, legacy: Double?): Double? {
        if (proposed == null || legacy == null) return null
        val legacyMagnitude = abs(legacy)
        val proposedMagnitude = abs(proposed)
        if (legacyMagnitude == 0.0) return if (proposedMagnitude == 0.0) 0.0 else Double.POSITIVE_INFINITY
        return (proposedMagnitude / legacyMagnitude - 1.0) * 100.0
    }

    private fun List<Double>.averageOrNull(): Double? = if (isEmpty()) null else average()
    private fun normalized(value: String): String = value.trim().uppercase().ifBlank { "UNKNOWN" }
}
