package com.analista.mobile.domain

import com.analista.mobile.data.FundamentalMetrics
import com.analista.mobile.data.FundamentalSnapshotEntity
import kotlin.math.round

object FundamentalAssessmentEngine {
    const val VERSION = "fundamental-assessment-1"

    data class Result(
        val score: Double,
        val coveragePct: Double,
        val status: String,
        val earningsRiskStatus: String,
        val reasons: List<String>
    )

    fun assess(metrics: FundamentalMetrics, nowUtcMillis: Long = System.currentTimeMillis()): Result {
        require(nowUtcMillis > 0L)
        val requested = listOf(
            metrics.revenueYoyPct,
            metrics.revenueTrend,
            metrics.epsYoyPct,
            metrics.epsTrend,
            metrics.grossMarginPct,
            metrics.grossMarginDeltaPct,
            metrics.operatingMarginPct,
            metrics.operatingMarginDeltaPct,
            metrics.profitMarginPct,
            metrics.netMarginDeltaPct,
            metrics.debtToEquity,
            metrics.debtToEbitda,
            metrics.interestCoverage,
            metrics.freeCashFlow,
            metrics.priceToSales,
            metrics.sectorPriceToSalesMedian,
            metrics.earningsDateUtc,
            metrics.dataAgeDays
        )
        val available = requested.count { it != null }
        val coveragePct = available.toDouble() / requested.size * 100.0
        val reasons = mutableListOf<String>()
        var score = 50.0

        metrics.revenueYoyPct?.let {
            score += when {
                it >= 20.0 -> 12.0
                it >= 8.0 -> 7.0
                it < 0.0 -> -12.0
                else -> 1.0
            }
            reasons += if (it >= 8.0) "revenue_growth_constructive" else if (it < 0.0) "revenue_declining" else "revenue_growth_muted"
        }
        when (metrics.revenueTrend?.uppercase()) {
            "IMPROVING" -> { score += 5.0; reasons += "revenue_trend_improving" }
            "DETERIORATING" -> { score -= 7.0; reasons += "revenue_trend_deteriorating" }
        }
        metrics.epsYoyPct?.let {
            score += when {
                it >= 20.0 -> 12.0
                it >= 8.0 -> 7.0
                it < 0.0 -> -12.0
                else -> 1.0
            }
            reasons += if (it >= 8.0) "eps_growth_constructive" else if (it < 0.0) "eps_declining" else "eps_growth_muted"
        }
        when (metrics.epsTrend?.uppercase()) {
            "IMPROVING" -> { score += 5.0; reasons += "eps_trend_improving" }
            "DETERIORATING" -> { score -= 7.0; reasons += "eps_trend_deteriorating" }
        }
        marginAdjustment(metrics.grossMarginDeltaPct, "gross", reasons).also { score += it }
        marginAdjustment(metrics.operatingMarginDeltaPct, "operating", reasons).also { score += it }
        marginAdjustment(metrics.netMarginDeltaPct, "net", reasons).also { score += it }

        metrics.debtToEbitda?.let {
            score += when {
                it < 0.0 -> -5.0
                it <= 2.0 -> 8.0
                it <= 3.5 -> 3.0
                it > 5.0 -> -10.0
                else -> -3.0
            }
            reasons += when {
                it <= 2.0 -> "debt_to_ebitda_conservative"
                it > 5.0 -> "debt_to_ebitda_high"
                else -> "debt_to_ebitda_moderate"
            }
        }
        metrics.interestCoverage?.let {
            score += when {
                it >= 8.0 -> 7.0
                it >= 4.0 -> 3.0
                it < 2.0 -> -10.0
                else -> -3.0
            }
            reasons += when {
                it >= 4.0 -> "interest_coverage_adequate"
                it < 2.0 -> "interest_coverage_weak"
                else -> "interest_coverage_thin"
            }
        }
        metrics.freeCashFlow?.let {
            score += if (it > 0.0) 5.0 else -7.0
            reasons += if (it > 0.0) "free_cash_flow_positive" else "free_cash_flow_negative"
        }
        if (metrics.priceToSales != null && metrics.sectorPriceToSalesMedian != null && metrics.sectorPriceToSalesMedian > 0.0) {
            val relative = metrics.priceToSales / metrics.sectorPriceToSalesMedian
            score += when {
                relative <= 0.8 -> 5.0
                relative >= 2.0 -> -7.0
                relative >= 1.4 -> -3.0
                else -> 1.0
            }
            reasons += when {
                relative <= 0.8 -> "price_to_sales_below_sector"
                relative >= 2.0 -> "price_to_sales_extreme_vs_sector"
                else -> "price_to_sales_near_sector"
            }
        } else {
            reasons += "sector_price_to_sales_unavailable"
        }

        val earningsSessions = metrics.earningsSessions ?: earningsSessions(metrics.earningsDateUtc, nowUtcMillis)
        val earningsRisk = when {
            earningsSessions == null -> "UNKNOWN"
            earningsSessions < 0 -> "PAST"
            earningsSessions <= 3 -> "IMMINENT"
            earningsSessions <= 7 -> "NEAR"
            else -> "CLEAR"
        }
        when (earningsRisk) {
            "IMMINENT" -> { score -= 15.0; reasons += "earnings_imminent" }
            "NEAR" -> { score -= 6.0; reasons += "earnings_near" }
            "UNKNOWN" -> reasons += "earnings_date_unknown"
        }

        val stale = metrics.dataAgeDays?.let { it > 180L } == true
        if (stale) { score -= 10.0; reasons += "fundamental_data_stale" }
        val status = when {
            available == 0 -> "EMPTY"
            stale -> "STALE"
            coveragePct >= 72.0 -> "COMPLETE"
            else -> "PARTIAL"
        }
        if (status == "PARTIAL") score -= 3.0
        if (status == "EMPTY") score = 50.0
        score = score.coerceIn(0.0, 100.0)
        return Result(round2(score), round2(coveragePct), status, earningsRisk, reasons.distinct())
    }

    fun toEntity(
        runId: String,
        ticker: String,
        metrics: FundamentalMetrics,
        capturedAtUtc: Long
    ): FundamentalSnapshotEntity {
        val result = assess(metrics, capturedAtUtc)
        return FundamentalSnapshotEntity(
            snapshotId = "$runId-${ticker.uppercase()}",
            runId = runId,
            ticker = ticker.uppercase(),
            revenueYoyPct = metrics.revenueYoyPct,
            revenueTrend = metrics.revenueTrend ?: "UNKNOWN",
            epsYoyPct = metrics.epsYoyPct,
            epsTrend = metrics.epsTrend ?: "UNKNOWN",
            grossMarginPct = metrics.grossMarginPct,
            grossMarginDeltaPct = metrics.grossMarginDeltaPct,
            operatingMarginPct = metrics.operatingMarginPct,
            operatingMarginDeltaPct = metrics.operatingMarginDeltaPct,
            netMarginPct = metrics.profitMarginPct,
            netMarginDeltaPct = metrics.netMarginDeltaPct,
            debtToEquity = metrics.debtToEquity,
            debtToEbitda = metrics.debtToEbitda,
            interestCoverage = metrics.interestCoverage,
            freeCashFlow = metrics.freeCashFlow,
            priceToSales = metrics.priceToSales,
            sectorPriceToSalesMedian = metrics.sectorPriceToSalesMedian,
            earningsDateUtc = metrics.earningsDateUtc,
            earningsSessions = metrics.earningsSessions ?: earningsSessions(metrics.earningsDateUtc, capturedAtUtc),
            earningsRiskStatus = result.earningsRiskStatus,
            dataAgeDays = metrics.dataAgeDays,
            sector = metrics.sector,
            coveragePct = result.coveragePct,
            status = result.status,
            fundamentalScore = result.score,
            reasons = result.reasons.joinToString(","),
            engineVersion = VERSION,
            capturedAtUtc = capturedAtUtc
        )
    }

    private fun marginAdjustment(delta: Double?, name: String, reasons: MutableList<String>): Double {
        if (delta == null) return 0.0
        return when {
            delta >= 2.0 -> { reasons += "${name}_margin_expanding"; 5.0 }
            delta <= -2.0 -> { reasons += "${name}_margin_contracting"; -7.0 }
            else -> { reasons += "${name}_margin_stable"; 1.0 }
        }
    }

    private fun earningsSessions(earningsDateUtc: Long?, nowUtcMillis: Long): Int? {
        if (earningsDateUtc == null || earningsDateUtc <= 0L) return null
        val today = java.time.Instant.ofEpochMilli(nowUtcMillis).atZone(NyseSessionCalendar.zoneId).toLocalDate()
        val earningsDate = java.time.Instant.ofEpochMilli(earningsDateUtc).atZone(NyseSessionCalendar.zoneId).toLocalDate()
        if (earningsDate.isBefore(today)) return -NyseSessionCalendar.sessionsBetween(earningsDate, today)
        return NyseSessionCalendar.sessionsBetween(today.minusDays(1), earningsDate)
    }

    private fun round2(value: Double) = round(value * 100.0) / 100.0
}
