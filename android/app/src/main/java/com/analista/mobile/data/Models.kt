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
    val source: String = "Yahoo Finance",
    val durationMs: Long = 0,
    val cacheHitCount: Int = 0,
    val retryCount: Int = 0
)

@Entity(
    tableName = "scan_candidates",
    foreignKeys = [ForeignKey(
        entity = ScanRunEntity::class,
        parentColumns = ["runId"],
        childColumns = ["runId"],
        onDelete = ForeignKey.CASCADE
    )],
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

@Entity(tableName = "backtest_outcomes", indices = [Index("ticker"), Index("sourceRunId")])
data class BacktestOutcomeEntity(
    @PrimaryKey val outcomeId: String,
    val sourceRunId: String,
    val ticker: String,
    val signal: String,
    val sourceClose: Double,
    val latestClose: Double,
    val returnPct: Double,
    val evaluatedAtUtc: Long
)

@Entity(tableName = "candidate_enrichment", indices = [Index("runId"), Index("ticker")])
data class CandidateEnrichmentEntity(
    @PrimaryKey val enrichmentId: String,
    val runId: String,
    val ticker: String,
    val marketCap: Long?,
    val trailingPe: Double?,
    val priceToSales: Double?,
    val epsTrailing: Double?,
    val revenueGrowthPct: Double?,
    val grossMarginPct: Double?,
    val operatingMarginPct: Double?,
    val profitMarginPct: Double?,
    val debtToEquity: Double?,
    val optionsPutCallOi: Double?,
    val optionsNearCallOi: Long?,
    val optionsNearPutOi: Long?,
    val optionsExpiry: Long?,
    val fundamentalsStatus: String,
    val optionsStatus: String,
    val capturedAtUtc: Long
)

@Entity(tableName = "market_snapshots")
data class MarketSnapshotEntity(
    @PrimaryKey val snapshotId: String,
    val runId: String,
    val symbol: String,
    val label: String,
    val close: Double,
    val changePct: Double,
    val capturedAtUtc: Long
)

data class PriceBar(
    val epochSeconds: Long,
    val open: Double,
    val high: Double,
    val low: Double,
    val close: Double,
    val volume: Long
)

data class FetchResult(
    val bars: List<PriceBar>,
    val source: String,
    val cacheHit: Boolean,
    val retries: Int
)

data class MarketQuote(
    val bid: Double?,
    val ask: Double?,
    val regularMarketPrice: Double?,
    val preMarketPrice: Double?,
    val marketCap: Long?,
    val quoteType: String?,
    val capturedAtUtc: Long = System.currentTimeMillis()
)

data class TradeContext(
    val quote: MarketQuote? = null,
    val marketCap: Long? = quote?.marketCap,
    val quoteType: String? = quote?.quoteType,
    val setupType: String = "BREAKOUT_OR_PULLBACK"
)

data class ScanCandidate(
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
    val reason: String,
    val quoteStatus: String = "MISSING",
    val executionQuoteQuality: String = "LOW",
    val triggerConfirmed: Boolean = false,
    val setupType: String = "BREAKOUT_OR_PULLBACK",
    val allVetoReasons: List<String> = emptyList(),
    val penaltyReasons: List<String> = emptyList(),
    val actionableEntry: Double? = entry,
    val actionableStop: Double? = stop,
    val actionableTarget: Double? = target,
    val theoreticalEntry: Double? = null,
    val theoreticalStop: Double? = null,
    val theoreticalTarget: Double? = null
)

data class FundamentalMetrics(
    val marketCap: Long?,
    val trailingPe: Double?,
    val priceToSales: Double?,
    val epsTrailing: Double?,
    val revenueGrowthPct: Double?,
    val grossMarginPct: Double?,
    val operatingMarginPct: Double?,
    val profitMarginPct: Double?,
    val debtToEquity: Double?
)

data class OptionsMetrics(
    val putCallOi: Double?,
    val nearCallOi: Long?,
    val nearPutOi: Long?,
    val expiry: Long?
)
