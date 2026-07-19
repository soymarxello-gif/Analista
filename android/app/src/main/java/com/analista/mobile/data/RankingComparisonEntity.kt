package com.analista.mobile.data

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "ranking_comparisons",
    indices = [Index("runId"), Index("status")]
)
data class RankingComparisonEntity(
    @PrimaryKey val comparisonId: String,
    val runId: String,
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
    val reasons: String,
    val engineVersion: String,
    val calculatedAtUtc: Long
)
