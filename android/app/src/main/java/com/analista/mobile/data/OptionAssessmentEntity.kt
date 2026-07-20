package com.analista.mobile.data

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "option_assessments",
    indices = [Index("runId"), Index("ticker"), Index("status"), Index("bias"), Index("conflict")]
)
data class OptionAssessmentEntity(
    @PrimaryKey val assessmentId: String,
    val runId: String,
    val ticker: String,
    val status: String,
    val coveragePct: Double,
    val putCallOiTotal: Double?,
    val putCallOiNearSpot: Double?,
    val callWallStrike: Double?,
    val putWallStrike: Double?,
    val callWallDistancePct: Double?,
    val putWallDistancePct: Double?,
    val oiConcentrationPct: Double?,
    val volumeToOiRatio: Double?,
    val ivSkewPutMinusCall: Double?,
    val gammaStatus: String,
    val bias: String,
    val optionsScore: Double,
    val institutionalScore: Double,
    val contrarianAdjustment: Double,
    val conflict: String,
    val reasons: String,
    val engineVersion: String,
    val capturedAtUtc: Long
)
