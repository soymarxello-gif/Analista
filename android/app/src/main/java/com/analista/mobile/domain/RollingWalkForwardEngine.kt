package com.analista.mobile.domain

import kotlin.random.Random

object RollingWalkForwardEngine {
    const val VERSION = "rolling-walk-forward-1"

    data class Config(
        val minimumTraining: Int = 120,
        val validationSize: Int = 40,
        val testSize: Int = 40,
        val stepSize: Int = 40,
        val embargoObservations: Int = 21,
        val minimumOutOfSampleClosed: Int = 200,
        val minimumExpectancyR: Double = 0.10,
        val bootstrapSamples: Int = 2_000,
        val randomSeed: Int = 7
    ) {
        init {
            require(minOf(minimumTraining, validationSize, testSize, stepSize, bootstrapSamples) > 0)
            require(embargoObservations >= 0)
        }
    }

    data class Fold(
        val number: Int,
        val training: List<WalkForwardStatisticsEngine.Observation>,
        val validation: List<WalkForwardStatisticsEngine.Observation>,
        val test: List<WalkForwardStatisticsEngine.Observation>
    )

    data class Report(
        val folds: List<Fold>,
        val outOfSampleClosed: Int,
        val expectancyR: Double?,
        val expectancyCi95: Pair<Double, Double>?,
        val eligibleForPromotion: Boolean,
        val reasons: List<String>,
        val version: String = VERSION
    )

    fun evaluate(
        observations: List<WalkForwardStatisticsEngine.Observation>,
        config: Config = Config()
    ): Report {
        require(observations.map { it.observationId }.distinct().size == observations.size)
        val ordered = observations.sortedWith(
            compareBy<WalkForwardStatisticsEngine.Observation> { it.decisionTimestampUtc }.thenBy { it.observationId }
        )
        val folds = mutableListOf<Fold>()
        var trainingEnd = config.minimumTraining
        var number = 1
        while (true) {
            val validationStart = trainingEnd + config.embargoObservations
            val validationEnd = validationStart + config.validationSize
            val testStart = validationEnd + config.embargoObservations
            val testEnd = testStart + config.testSize
            if (testEnd > ordered.size) break
            folds += Fold(
                number = number++,
                training = ordered.take(trainingEnd),
                validation = ordered.subList(validationStart, validationEnd),
                test = ordered.subList(testStart, testEnd)
            )
            trainingEnd += config.stepSize
        }
        val outOfSample = folds.flatMap { it.test }.distinctBy { it.observationId }
        val closed = outOfSample.filter { it.activated && it.tradeReturnR != null }
        val returns = closed.map { it.tradeReturnR!! }
        val expectancy = returns.takeIf { it.isNotEmpty() }?.average()
        val ci = returns.takeIf { it.isNotEmpty() }?.let { bootstrapCi(it, config) }
        val reasons = buildList {
            if (folds.isEmpty()) add("no_complete_rolling_fold")
            if (closed.size < config.minimumOutOfSampleClosed) add("insufficient_oos_closed")
            if (outOfSample.any { !it.p0Valid }) add("p0_regression_present")
            if (expectancy == null || expectancy < config.minimumExpectancyR) add("expectancy_below_gate")
            if (ci == null || ci.first <= 0.0) add("expectancy_confidence_interval_crosses_zero")
        }
        return Report(folds, closed.size, expectancy, ci, reasons.isEmpty(), reasons.distinct())
    }

    private fun bootstrapCi(values: List<Double>, config: Config): Pair<Double, Double> {
        val random = Random(config.randomSeed)
        val estimates = List(config.bootstrapSamples) {
            List(values.size) { values[random.nextInt(values.size)] }.average()
        }.sorted()
        val lower = estimates[((estimates.size - 1) * 0.025).toInt()]
        val upper = estimates[((estimates.size - 1) * 0.975).toInt()]
        return lower to upper
    }
}
