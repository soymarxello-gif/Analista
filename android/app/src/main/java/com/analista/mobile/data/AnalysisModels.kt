package com.analista.mobile.data

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "candidate_analysis",
    indices = [Index("runId"), Index("ticker"), Index("finalTradeScore")]
)
data class CandidateAnalysisEntity(
    @PrimaryKey val analysisId: String,
    val runId: String,
    val ticker: String,
    val rsi6: Double,
    val rsi14Canonical: Double,
    val rsi6GtRsi14: Boolean,
    val ema20: Double,
    val ema50: Double,
    val ema200: Double,
    val priceVsEma20Pct: Double,
    val priceVsEma50Pct: Double,
    val priceVsEma200Pct: Double,
    val weeklyTrend: String,
    val assetQualityScore: Double,
    val setupQualityScore: Double,
    val contextScore: Double,
    val institutionalScore: Double,
    val riskScore: Double,
    val finalTradeScore: Double,
    val stopAtrMultiple: Double,
    val stopAtrStatus: String,
    val scoreBreakdown: String,
    val engineVersion: String,
    val calculatedAtUtc: Long
)

data class CanonicalAnalysis(
    val rsi6: Double,
    val rsi14: Double,
    val ema20: Double,
    val ema50: Double,
    val ema200: Double,
    val macd: Double,
    val macdSignal: Double,
    val atr14: Double,
    val weeklyTrend: String,
    val assetQualityScore: Double,
    val setupQualityScore: Double,
    val contextScore: Double,
    val institutionalScore: Double,
    val riskScore: Double,
    val finalTradeScore: Double,
    val stopAtrMultiple: Double,
    val stopAtrStatus: String,
    val scoreBreakdown: String
)

data class AnalyzedCandidate(
    val candidate: ScanCandidate,
    val analysis: CanonicalAnalysis
)
