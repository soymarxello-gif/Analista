package com.analista.mobile.ui

import com.analista.mobile.data.RankingComparisonEntity

object RankingDiagnosticsPresenter {
    data class Model(
        val available: Boolean,
        val status: String,
        val adoptionLabel: String,
        val comparableItems: Int,
        val totalItems: Int,
        val topK: Int,
        val topKOverlapPct: Double?,
        val spearman: Double?,
        val medianAbsoluteDisplacement: Double?,
        val missingItems: Int,
        val reasons: List<String>,
        val compactLabel: String
    )

    fun present(entity: RankingComparisonEntity?): Model {
        if (entity == null) {
            return Model(
                available = false,
                status = "NO_DATA",
                adoptionLabel = "Ranking legacy activo",
                comparableItems = 0,
                totalItems = 0,
                topK = 0,
                topKOverlapPct = null,
                spearman = null,
                medianAbsoluteDisplacement = null,
                missingItems = 0,
                reasons = listOf("COMPARISON_NOT_AVAILABLE"),
                compactLabel = "Ranking: sin comparación · legacy activo"
            )
        }
        val overlap = "%.1f".format(entity.topKOverlapPct)
        val spearman = entity.spearman?.let { "%.4f".format(it) } ?: "—"
        val displacement = entity.medianAbsoluteDisplacement?.let { "%.2f".format(it) } ?: "—"
        return Model(
            available = true,
            status = entity.status,
            adoptionLabel = if (entity.thresholdsPassed) {
                "Comparación estable; requiere validación histórica antes de adopción"
            } else {
                "Ranking legacy activo"
            },
            comparableItems = entity.comparableItems,
            totalItems = entity.totalItems,
            topK = entity.topK,
            topKOverlapPct = entity.topKOverlapPct,
            spearman = entity.spearman,
            medianAbsoluteDisplacement = entity.medianAbsoluteDisplacement,
            missingItems = entity.missingItems,
            reasons = entity.reasons.split(',').map { it.trim() }.filter { it.isNotBlank() },
            compactLabel = "Ranking ${entity.status}: top-${entity.topK} $overlap% · Spearman $spearman · Δmed $displacement · faltantes ${entity.missingItems} · legacy activo"
        )
    }
}
