package com.analista.mobile.data

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "fundamental_snapshots",
    indices = [Index("runId"), Index("ticker"), Index("status"), Index("earningsRiskStatus")]
)
data class FundamentalSnapshotEntity(
    @PrimaryKey val snapshotId: String,
    val runId: String,
    val ticker: String,
    val revenueYoyPct: Double?,
    val revenueTrend: String,
    val epsYoyPct: Double?,
    val epsTrend: String,
    val grossMarginPct: Double?,
    val grossMarginDeltaPct: Double?,
    val operatingMarginPct: Double?,
    val operatingMarginDeltaPct: Double?,
    val netMarginPct: Double?,
    val netMarginDeltaPct: Double?,
    val debtToEquity: Double?,
    val debtToEbitda: Double?,
    val interestCoverage: Double?,
    val freeCashFlow: Double?,
    val priceToSales: Double?,
    val sectorPriceToSalesMedian: Double?,
    val earningsDateUtc: Long?,
    val earningsSessions: Int?,
    val earningsRiskStatus: String,
    val dataAgeDays: Long?,
    val sector: String?,
    val coveragePct: Double,
    val status: String,
    val fundamentalScore: Double,
    val reasons: String,
    val engineVersion: String,
    val capturedAtUtc: Long
)
