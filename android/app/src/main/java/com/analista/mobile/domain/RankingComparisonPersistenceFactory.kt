package com.analista.mobile.domain

import com.analista.mobile.data.CandidateTradePlanEntity
import com.analista.mobile.data.RankingComparisonEntity

object RankingComparisonPersistenceFactory {
    const val VERSION = "ranking-comparison-persistence-1"

    fun create(rows: List<CandidateTradePlanEntity>, calculatedAtUtc: Long): RankingComparisonEntity? {
        if (rows.isEmpty()) return null
        require(calculatedAtUtc > 0L) { "timestamp inválido" }
        val runIds = rows.map { it.runId }.toSet()
        require(runIds.size == 1) { "planes de múltiples corridas" }
        val runId = runIds.single()
        require(runId.isNotBlank()) { "runId vacío" }

        val summary = RankingComparisonEngine.compare(rows.map { row ->
            RankingComparisonEngine.Item(
                ticker = row.ticker,
                legacyRank = row.legacyRank,
                tradeRank = row.tradeRank
            )
        })
        return RankingComparisonEntity(
            comparisonId = runId,
            runId = runId,
            totalItems = summary.totalItems,
            comparableItems = summary.comparableItems,
            missingItems = summary.missingItems,
            topK = summary.topK,
            topKOverlapCount = summary.topKOverlapCount,
            topKOverlapPct = summary.topKOverlapPct,
            medianAbsoluteDisplacement = summary.medianAbsoluteDisplacement,
            spearman = summary.spearman,
            thresholdsPassed = summary.thresholdsPassed,
            status = summary.status,
            reasons = summary.reasons.joinToString(","),
            engineVersion = "${summary.engineVersion}+$VERSION",
            calculatedAtUtc = calculatedAtUtc
        )
    }
}