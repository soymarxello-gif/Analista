package com.analista.mobile.data

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "candidate_trade_plans",
    indices = [Index("runId"), Index("ticker"), Index("tradeRank")]
)
data class CandidateTradePlanEntity(
    @PrimaryKey val planId: String,
    val runId: String,
    val ticker: String,
    val priorResistance: Double,
    val nextResistance: Double?,
    val swingLow: Double,
    val closeLocationValue: Double,
    val baseRangeAtr: Double,
    val volatilityCompression: Double,
    val resistanceTouches: Int,
    val structureScore: Double,
    val rs20VsSpy: Double?,
    val rs60VsSpy: Double?,
    val relativeStrengthScore: Double,
    val relativeStrengthStatus: String,
    val plannedEntry: Double,
    val structuralStop: Double,
    val structuralTarget: Double,
    val stopType: String,
    val stopAtrMultiple: Double,
    val structuralRr: Double,
    val riskPct: Double,
    val rewardPct: Double,
    val shares: Int,
    val positionValue: Double,
    val riskBudget: Double,
    val riskPlanValid: Boolean,
    val legacyRank: Int,
    val tradeRank: Int,
    val rankDelta: Int,
    val auditedTradeScore: Double,
    val reasons: String,
    val engineVersion: String,
    val calculatedAtUtc: Long
)
