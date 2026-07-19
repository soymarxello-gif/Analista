package com.analista.mobile.data

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "final_decisions",
    indices = [
        Index(value = ["runId"]),
        Index(value = ["ticker"]),
        Index(value = ["finalSignal"]),
        Index(value = ["eligibleForContract"])
    ]
)
data class FinalDecisionEntity(
    @PrimaryKey val decisionId: String,
    val runId: String,
    val ticker: String,
    val preliminarySignal: String,
    val finalSignal: String,
    val finalTradeScore: Double,
    val eligibleForContract: Boolean,
    val confidence: String,
    val vetoReasons: String,
    val penaltyReasons: String,
    val macroRegime: String,
    val fundamentalCoverage: String,
    val institutionalCoverage: String,
    val executionFreshness: String,
    val decisionVersion: String,
    val calculatedAtUtc: Long
)