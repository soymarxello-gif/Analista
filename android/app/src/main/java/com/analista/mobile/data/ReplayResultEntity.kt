package com.analista.mobile.data

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "replay_results",
    indices = [Index("runId"), Index("status"), Index("evaluatedAtUtc")]
)
data class ReplayResultEntity(
    @PrimaryKey val replayId: String,
    val runId: String,
    val status: String,
    val expectedTickers: Int,
    val replayedTickers: Int,
    val fullyMatchedTickers: Int,
    val mismatchedTickers: Int,
    val missingDatasetCount: Int,
    val reasons: String,
    val tickerDetails: String,
    val engineVersion: String,
    val evaluatedAtUtc: Long
)
