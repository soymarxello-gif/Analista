package com.analista.mobile.domain

import kotlin.math.abs
import kotlin.math.round

object RankingComparisonEngine {
    const val VERSION = "ranking-comparison-1"

    data class Item(
        val ticker: String,
        val legacyRank: Int?,
        val tradeRank: Int?
    )

    data class Thresholds(
        val minimumComparableItems: Int = 20,
        val topK: Int = 5,
        val minimumTopKOverlapPct: Double = 60.0,
        val minimumSpearman: Double = 0.70,
        val maximumMedianAbsoluteDisplacement: Double = 5.0,
        val maximumMissingItems: Int = 0
    )

    data class Summary(
        val totalItems: Int,
        val comparableItems: Int,
        val missingItems: Int,
        val topK: Int,
        val topKOverlapCount: Int,
        val topKOverlapPct: Double,
        val medianAbsoluteDisplacement: Double?,
        val spearman: Double?,
        val thresholdsPassed: Boolean,
        val status: String,
        val reasons: List<String>,
        val engineVersion: String = VERSION
    )

    fun compare(items: List<Item>, thresholds: Thresholds = Thresholds()): Summary {
        require(thresholds.minimumComparableItems > 1)
        require(thresholds.topK > 0)
        require(thresholds.minimumTopKOverlapPct in 0.0..100.0)
        require(thresholds.minimumSpearman in -1.0..1.0)
        require(thresholds.maximumMedianAbsoluteDisplacement >= 0.0)
        require(thresholds.maximumMissingItems >= 0)

        val normalized = items.map {
            it.copy(ticker = it.ticker.trim().uppercase())
        }
        require(normalized.all { it.ticker.isNotBlank() })
        require(normalized.map { it.ticker }.distinct().size == normalized.size) { "tickers duplicados" }

        val comparable = normalized.filter { it.legacyRank != null && it.tradeRank != null }
        validateRanks(comparable.mapNotNull { it.legacyRank }, "legacy")
        validateRanks(comparable.mapNotNull { it.tradeRank }, "trade")

        val missing = normalized.size - comparable.size
        val effectiveK = minOf(thresholds.topK, comparable.size)
        val legacyTop = comparable.sortedBy { it.legacyRank }.take(effectiveK).map { it.ticker }.toSet()
        val tradeTop = comparable.sortedBy { it.tradeRank }.take(effectiveK).map { it.ticker }.toSet()
        val overlapCount = legacyTop.intersect(tradeTop).size
        val overlapPct = if (effectiveK == 0) 0.0 else overlapCount * 100.0 / effectiveK

        val displacements = comparable.map { abs(it.legacyRank!! - it.tradeRank!!).toDouble() }.sorted()
        val median = median(displacements)
        val spearman = if (comparable.size < 2) null else {
            val sumSquared = comparable.sumOf {
                val difference = it.legacyRank!! - it.tradeRank!!
                difference.toDouble() * difference.toDouble()
            }
            val n = comparable.size.toDouble()
            1.0 - (6.0 * sumSquared) / (n * (n * n - 1.0))
        }

        val reasons = buildList {
            if (comparable.size < thresholds.minimumComparableItems) add("INSUFFICIENT_SAMPLE")
            if (missing > thresholds.maximumMissingItems) add("MISSING_RANKS")
            if (effectiveK < thresholds.topK) add("TOP_K_NOT_AVAILABLE")
            if (effectiveK > 0 && overlapPct < thresholds.minimumTopKOverlapPct) add("LOW_TOP_K_OVERLAP")
            if (spearman == null || spearman < thresholds.minimumSpearman) add("LOW_RANK_CORRELATION")
            if (median == null || median > thresholds.maximumMedianAbsoluteDisplacement) add("HIGH_MEDIAN_DISPLACEMENT")
        }
        val passed = reasons.isEmpty()
        return Summary(
            totalItems = normalized.size,
            comparableItems = comparable.size,
            missingItems = missing,
            topK = effectiveK,
            topKOverlapCount = overlapCount,
            topKOverlapPct = round2(overlapPct),
            medianAbsoluteDisplacement = median?.let(::round2),
            spearman = spearman?.let { round(it * 10_000.0) / 10_000.0 },
            thresholdsPassed = passed,
            status = if (passed) "SHADOW_COMPARISON_STABLE" else "KEEP_LEGACY_ORDER",
            reasons = reasons
        )
    }

    private fun validateRanks(ranks: List<Int>, label: String) {
        require(ranks.all { it > 0 }) { "rank $label inválido" }
        require(ranks.distinct().size == ranks.size) { "rank $label duplicado" }
    }

    private fun median(values: List<Double>): Double? {
        if (values.isEmpty()) return null
        val middle = values.size / 2
        return if (values.size % 2 == 1) values[middle] else (values[middle - 1] + values[middle]) / 2.0
    }

    private fun round2(value: Double): Double = round(value * 100.0) / 100.0
}
