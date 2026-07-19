package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar

object TradePlanGenerationEngine {
    const val ENGINE_VERSION = "trade-plan-generation-1"

    data class Input(
        val ticker: String,
        val signal: String,
        val setupType: String,
        val legacyScore: Double,
        val finalTradeScore: Double,
        val bars: List<PriceBar>,
        val benchmarkBars: List<PriceBar>?,
        val entry: Double,
        val atr: Double,
        val sma20: Double,
        val equity: Double = 25_000.0,
        val riskPctOfEquity: Double = 0.01,
        val maxPositionPct: Double = 0.20
    )

    data class Generated(
        val ticker: String,
        val structure: StructureRiskEngine.StructureAssessment,
        val relativeStrength: RelativeStrengthEngine.Result?,
        val riskPlan: StructureRiskEngine.RiskPlan,
        val legacyRank: Int,
        val tradeRank: Int,
        val rankDelta: Int,
        val auditedTradeScore: Double,
        val eligibleForOperationalRanking: Boolean,
        val reasons: List<String>
    )

    fun generate(inputs: List<Input>): List<Generated> {
        if (inputs.isEmpty()) return emptyList()

        data class Intermediate(
            val input: Input,
            val structure: StructureRiskEngine.StructureAssessment,
            val relativeStrength: RelativeStrengthEngine.Result?,
            val riskPlan: StructureRiskEngine.RiskPlan
        )

        val intermediate = inputs.map { input ->
            require(input.bars.size >= 60) { "Insufficient bars for ${input.ticker}" }
            val structure = StructureRiskEngine.assess(input.bars, input.atr)
            val relativeStrength = input.benchmarkBars
                ?.takeIf { input.bars.size >= 61 && it.size >= 61 }
                ?.let { benchmark -> runCatching { RelativeStrengthEngine.compare(input.bars, benchmark) }.getOrNull() }
            val riskPlan = StructureRiskEngine.plan(
                entry = input.entry,
                atr = input.atr,
                sma20 = input.sma20,
                swingLow = structure.swingLow,
                nextResistance = structure.nextResistance,
                equity = input.equity,
                riskPctOfEquity = input.riskPctOfEquity,
                maxPositionPct = input.maxPositionPct
            )
            Intermediate(input, structure, relativeStrength, riskPlan)
        }

        val ranked = RankingAuditEngine.compare(intermediate.map { row ->
            RankingAuditEngine.Input(
                ticker = row.input.ticker,
                signal = row.input.signal,
                setupType = row.input.setupType,
                legacyScore = row.input.legacyScore,
                finalTradeScore = row.input.finalTradeScore,
                structureScore = row.structure.structureScore,
                relativeStrengthScore = row.relativeStrength?.score ?: 50.0,
                riskPlanValid = row.riskPlan.valid
            )
        }).associateBy { it.ticker }

        return intermediate.map { row ->
            val rank = ranked.getValue(row.input.ticker)
            Generated(
                ticker = row.input.ticker,
                structure = row.structure,
                relativeStrength = row.relativeStrength,
                riskPlan = row.riskPlan,
                legacyRank = rank.legacyRank,
                tradeRank = rank.tradeRank,
                rankDelta = rank.rankDelta,
                auditedTradeScore = rank.protectedTradeScore,
                eligibleForOperationalRanking = rank.eligibleForOperationalRanking,
                reasons = buildList {
                    addAll(row.structure.reasons)
                    addAll(row.riskPlan.reasons)
                    if (row.relativeStrength == null) add("relative_strength_unavailable")
                    if (!rank.eligibleForOperationalRanking) add("operational_ranking_ineligible")
                }.distinct()
            )
        }.sortedBy { it.tradeRank }
    }
}
