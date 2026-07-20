package com.analista.mobile.domain

import kotlin.math.abs
import kotlin.math.floor

object WalkForwardStatisticsEngine {
    const val VERSION = "walk-forward-statistics-1"

    data class Observation(
        val observationId: String,
        val decisionTimestampUtc: Long,
        val setupType: String,
        val macroRegime: String,
        val sector: String = "UNKNOWN",
        val activated: Boolean,
        val tradeReturnR: Double?,
        val mfePct: Double?,
        val maePct: Double?,
        val holdingSessions: Int,
        val status: String,
        val p0Valid: Boolean = true
    )

    data class PartitionConfig(
        val trainingPct: Double = 0.60,
        val validationPct: Double = 0.20
    ) {
        init {
            require(trainingPct in 0.0..1.0)
            require(validationPct in 0.0..1.0)
            require(trainingPct + validationPct < 1.0)
        }
    }

    data class Thresholds(
        val minimumOutOfSampleClosed: Int = 100,
        val minimumDominantSetupClosed: Int = 30,
        val dominantSetupMinSharePct: Double = 20.0,
        val minimumDistinctRegimes: Int = 2
    )

    data class Metrics(
        val totalObservations: Int,
        val activated: Int,
        val closedWithReturn: Int,
        val expectancyR: Double?,
        val medianR: Double?,
        val hitRatePct: Double?,
        val profitFactor: Double?,
        val maximumDrawdownR: Double?,
        val averageMfePct: Double?,
        val averageMaePct: Double?,
        val averageHoldingSessions: Double?
    )

    data class Partition(
        val name: String,
        val firstTimestampUtc: Long?,
        val lastTimestampUtc: Long?,
        val metrics: Metrics
    )

    data class GroupMetrics(
        val key: String,
        val metrics: Metrics
    )

    data class Summary(
        val training: Partition,
        val validation: Partition,
        val test: Partition,
        val testBySetup: List<GroupMetrics>,
        val testByRegime: List<GroupMetrics>,
        val testBySector: List<GroupMetrics>,
        val eligibleForRankingPromotion: Boolean,
        val reasons: List<String>,
        val engineVersion: String = VERSION
    )

    fun evaluate(
        observations: List<Observation>,
        partitionConfig: PartitionConfig = PartitionConfig(),
        thresholds: Thresholds = Thresholds()
    ): Summary {
        require(thresholds.minimumOutOfSampleClosed > 0)
        require(thresholds.minimumDominantSetupClosed > 0)
        require(thresholds.dominantSetupMinSharePct in 0.0..100.0)
        require(thresholds.minimumDistinctRegimes > 0)
        require(observations.map { it.observationId }.distinct().size == observations.size) {
            "observationId must be unique"
        }
        require(observations.all { it.observationId.isNotBlank() && it.decisionTimestampUtc > 0L })
        require(observations.all { it.holdingSessions >= 0 })
        require(observations.all { it.tradeReturnR == null || it.tradeReturnR.isFinite() })

        val ordered = observations.sortedWith(compareBy<Observation> { it.decisionTimestampUtc }.thenBy { it.observationId })
        val trainingEnd = floor(ordered.size * partitionConfig.trainingPct).toInt()
        val validationEnd = trainingEnd + floor(ordered.size * partitionConfig.validationPct).toInt()
        val trainingRows = ordered.take(trainingEnd)
        val validationRows = ordered.subList(trainingEnd, validationEnd.coerceAtMost(ordered.size))
        val testRows = ordered.drop(validationEnd.coerceAtMost(ordered.size))

        val reasons = mutableListOf<String>()
        val testClosed = testRows.count { it.activated && it.tradeReturnR != null }
        if (testClosed < thresholds.minimumOutOfSampleClosed) reasons += "insufficient_out_of_sample_closed"
        if (testRows.any { !it.p0Valid }) reasons += "p0_regression_present"

        val closedBySetup = testRows
            .filter { it.activated && it.tradeReturnR != null }
            .groupingBy { normalized(it.setupType) }
            .eachCount()
        val dominantMinimumCount = testClosed * thresholds.dominantSetupMinSharePct / 100.0
        val dominantSetups = closedBySetup.filterValues { it >= dominantMinimumCount }
        if (dominantSetups.isEmpty()) reasons += "no_dominant_setup_in_test"
        dominantSetups.filterValues { it < thresholds.minimumDominantSetupClosed }.keys.sorted().forEach {
            reasons += "insufficient_dominant_setup:$it"
        }

        val distinctRegimes = testRows
            .filter { it.activated && it.tradeReturnR != null }
            .map { normalized(it.macroRegime) }
            .filter { it != "UNKNOWN" }
            .distinct()
            .size
        if (distinctRegimes < thresholds.minimumDistinctRegimes) reasons += "insufficient_market_regimes"

        return Summary(
            training = partition("TRAINING", trainingRows),
            validation = partition("VALIDATION", validationRows),
            test = partition("TEST", testRows),
            testBySetup = grouped(testRows) { it.setupType },
            testByRegime = grouped(testRows) { it.macroRegime },
            testBySector = grouped(testRows) { it.sector },
            eligibleForRankingPromotion = reasons.isEmpty(),
            reasons = reasons.distinct()
        )
    }

    private fun partition(name: String, rows: List<Observation>) = Partition(
        name = name,
        firstTimestampUtc = rows.firstOrNull()?.decisionTimestampUtc,
        lastTimestampUtc = rows.lastOrNull()?.decisionTimestampUtc,
        metrics = metrics(rows)
    )

    private fun grouped(
        rows: List<Observation>,
        selector: (Observation) -> String
    ): List<GroupMetrics> = rows
        .groupBy { normalized(selector(it)) }
        .map { (key, values) -> GroupMetrics(key, metrics(values)) }
        .sortedWith(compareByDescending<GroupMetrics> { it.metrics.closedWithReturn }.thenBy { it.key })

    private fun metrics(rows: List<Observation>): Metrics {
        val activated = rows.filter { it.activated }
        val closed = activated.filter { it.tradeReturnR != null }
        val returns = closed.map { it.tradeReturnR!! }
        val wins = returns.filter { it > 0.0 }
        val losses = returns.filter { it < 0.0 }
        val profitFactor = if (losses.isNotEmpty()) wins.sum() / abs(losses.sum()) else null

        var cumulative = 0.0
        var peak = 0.0
        var maxDrawdown = 0.0
        for (value in returns) {
            cumulative += value
            peak = maxOf(peak, cumulative)
            maxDrawdown = maxOf(maxDrawdown, peak - cumulative)
        }

        return Metrics(
            totalObservations = rows.size,
            activated = activated.size,
            closedWithReturn = closed.size,
            expectancyR = returns.averageOrNull(),
            medianR = median(returns),
            hitRatePct = returns.takeIf { it.isNotEmpty() }?.let { values ->
                values.count { it > 0.0 } * 100.0 / values.size
            },
            profitFactor = profitFactor,
            maximumDrawdownR = returns.takeIf { it.isNotEmpty() }?.let { maxDrawdown },
            averageMfePct = activated.mapNotNull { it.mfePct }.averageOrNull(),
            averageMaePct = activated.mapNotNull { it.maePct }.averageOrNull(),
            averageHoldingSessions = activated.map { it.holdingSessions.toDouble() }.averageOrNull()
        )
    }

    private fun median(values: List<Double>): Double? {
        if (values.isEmpty()) return null
        val sorted = values.sorted()
        val middle = sorted.size / 2
        return if (sorted.size % 2 == 1) sorted[middle] else (sorted[middle - 1] + sorted[middle]) / 2.0
    }

    private fun List<Double>.averageOrNull(): Double? = if (isEmpty()) null else average()
    private fun normalized(value: String): String = value.trim().uppercase().ifBlank { "UNKNOWN" }
}
