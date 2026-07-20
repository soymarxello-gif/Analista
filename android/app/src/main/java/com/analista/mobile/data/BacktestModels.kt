package com.analista.mobile.data

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "signal_contracts",
    indices = [Index("runId"), Index("ticker"), Index("decisionTimestampUtc")]
)
data class SignalContractEntity(
    @PrimaryKey val signalId: String,
    val runId: String,
    val ticker: String,
    val signal: String,
    val decisionTimestampUtc: Long,
    val referencePrice: Double,
    val triggerPrice: Double,
    val maximumEntry: Double,
    val stopPrice: Double,
    val targetPrice: Double,
    val expirationSessions: Int,
    val engineVersion: String,
    val createdAtUtc: Long,
    @ColumnInfo(defaultValue = "0") val shares: Int = 0,
    @ColumnInfo(defaultValue = "0") val positionValue: Double = 0.0,
    @ColumnInfo(defaultValue = "0") val riskBudget: Double = 0.0
)

@Entity(
    tableName = "trade_outcomes",
    indices = [Index("ticker"), Index("evaluatedAtUtc")]
)
data class TradeOutcomeEntity(
    @PrimaryKey val signalId: String,
    val ticker: String,
    val evaluatedAtUtc: Long,
    val triggered: Boolean,
    val triggerTimestampUtc: Long?,
    val entryFill: Double?,
    val stopHit: Boolean,
    val targetHit: Boolean,
    val firstExitEvent: String,
    val return1dPct: Double?,
    val return3dPct: Double?,
    val return5dPct: Double?,
    val return10dPct: Double?,
    val return20dPct: Double?,
    val mfePct: Double?,
    val maePct: Double?,
    val holdingSessions: Int,
    val ambiguousSameBar: Boolean,
    val status: String,
    val exitTimestampUtc: Long? = null,
    val exitFill: Double? = null,
    @ColumnInfo(defaultValue = "'NONE'") val exitReason: String = "NONE",
    val tradeReturnPct: Double? = null,
    val tradeReturnR: Double? = null,
    val grossPnl: Double? = null,
    val netPnl: Double? = null,
    val totalCosts: Double? = null,
    @ColumnInfo(defaultValue = "'legacy-zero-cost'") val costModelVersion: String = "legacy-zero-cost"
)
