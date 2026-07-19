package com.analista.mobile.data

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(tableName = "scan_runs")
data class ScanRunEntity(
    @PrimaryKey val runId: String,
    val startedAtUtc: Long,
    val finishedAtUtc: Long,
    val marketDateEt: String,
    val status: String,
    val trustStatus: String,
    val candidateCount: Int,
    val failureCount: Int,
    val source: String = "Yahoo Finance"
)

@Entity(
    tableName = "scan_candidates",
    foreignKeys = [ForeignKey(entity = ScanRunEntity::class, parentColumns = ["runId"], childColumns = ["runId"], onDelete = ForeignKey.CASCADE)],
    indices = [Index("runId"), Index("ticker")]
)
data class CandidateEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val runId: String,
    val ticker: String,
    val signal: String,
    val score: Double,
    val close: Double,
    val sma20: Double,
    val sma50: Double,
    val rsi14: Double,
    val macd: Double,
    val macdSignal: Double,
    val stochastic: Double,
    val atr14: Double,
    val relativeVolume: Double,
    val entry: Double?,
    val stop: Double?,
    val target: Double?,
    val rr: Double?,
    val reason: String
)

data class PriceBar(val epochSeconds: Long, val open: Double, val high: Double, val low: Double, val close: Double, val volume: Long)

data class ScanCandidate(
    val ticker: String, val signal: String, val score: Double, val close: Double,
    val sma20: Double, val sma50: Double, val rsi14: Double, val macd: Double,
    val macdSignal: Double, val stochastic: Double, val atr14: Double,
    val relativeVolume: Double, val entry: Double?, val stop: Double?,
    val target: Double?, val rr: Double?, val reason: String
)
