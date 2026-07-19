package com.analista.mobile.domain

object RankingAuditEngine {
    data class Input(
        val ticker: String,
        val signal: String,
        val setupType: String,
        val legacyScore: Double,
        val finalTradeScore: Double,
        val structureScore: Double,
        val relativeStrengthScore: Double,
        val riskPlanValid: Boolean
    )

    data class Ranked(
        val ticker: String,
        val legacyRank: Int,
        val tradeRank: Int,
        val rankDelta: Int,
        val protectedTradeScore: Double,
        val eligibleForOperationalRanking: Boolean
    )

    fun compare(rows: List<Input>): List<Ranked> {
        if (rows.isEmpty()) return emptyList()
        val protected = rows.associateWith { row -> protectedScore(row) }
        val legacyOrder = rows.sortedWith(compareByDescending<Input> { it.legacyScore }.thenBy { it.ticker })
        val tradeOrder = rows.sortedWith(
            compareByDescending<Input> { protected.getValue(it) }
                .thenByDescending { it.structureScore }
                .thenByDescending { it.relativeStrengthScore }
                .thenBy { it.ticker }
        )
        val legacyRanks = legacyOrder.mapIndexed { index, row -> row.ticker to index + 1 }.toMap()
        val tradeRanks = tradeOrder.mapIndexed { index, row -> row.ticker to index + 1 }.toMap()
        return rows.map { row ->
            val legacyRank = legacyRanks.getValue(row.ticker)
            val tradeRank = tradeRanks.getValue(row.ticker)
            Ranked(
                ticker = row.ticker,
                legacyRank = legacyRank,
                tradeRank = tradeRank,
                rankDelta = legacyRank - tradeRank,
                protectedTradeScore = protected.getValue(row),
                eligibleForOperationalRanking = isEligible(row)
            )
        }.sortedBy { it.tradeRank }
    }

    internal fun protectedScore(row: Input): Double {
        if (!isEligible(row)) return minOf(row.finalTradeScore, 49.0)
        val structureAdjustment = (row.structureScore - 50.0) * 0.10
        val rsAdjustment = (row.relativeStrengthScore - 50.0) * 0.08
        val riskAdjustment = if (row.riskPlanValid) 3.0 else -12.0
        return (row.finalTradeScore + structureAdjustment + rsAdjustment + riskAdjustment)
            .coerceIn(0.0, 100.0)
    }

    private fun isEligible(row: Input): Boolean =
        row.signal != "VETO" && row.setupType != "NO_VALID_SETUP"
}
