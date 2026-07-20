package com.analista.mobile.domain

import com.analista.mobile.data.FundamentalMetrics
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

class FundamentalAssessmentEngineTest {
    private val now = Instant.parse("2026-07-20T13:00:00Z").toEpochMilli()

    private fun metrics(
        earningsDateUtc: Long? = Instant.parse("2026-08-20T20:00:00Z").toEpochMilli(),
        dataAgeDays: Long = 45L
    ) = FundamentalMetrics(
        marketCap = 100_000_000_000L,
        trailingPe = 25.0,
        priceToSales = 4.0,
        epsTrailing = 5.0,
        revenueGrowthPct = 18.0,
        grossMarginPct = 62.0,
        operatingMarginPct = 28.0,
        profitMarginPct = 22.0,
        debtToEquity = 55.0,
        revenueYoyPct = 18.0,
        revenueTrend = "IMPROVING",
        epsYoyPct = 24.0,
        epsTrend = "IMPROVING",
        grossMarginDeltaPct = 2.5,
        operatingMarginDeltaPct = 2.0,
        netMarginDeltaPct = 1.5,
        debtToEbitda = 1.8,
        interestCoverage = 10.0,
        freeCashFlow = 5_000_000_000.0,
        sectorPriceToSalesMedian = 5.0,
        earningsDateUtc = earningsDateUtc,
        dataAgeDays = dataAgeDays,
        sector = "Technology"
    )

    @Test
    fun improvingTemporalFundamentalsProduceCompleteHighScore() {
        val result = FundamentalAssessmentEngine.assess(metrics(), now)
        assertEquals("COMPLETE", result.status)
        assertEquals("CLEAR", result.earningsRiskStatus)
        assertTrue(result.score >= 75.0)
        assertTrue(result.coveragePct >= 72.0)
        assertTrue("eps_trend_improving" in result.reasons)
    }

    @Test
    fun imminentEarningsApplyStrongPenaltyWithoutUniversalVeto() {
        val imminent = Instant.parse("2026-07-22T20:00:00Z").toEpochMilli()
        val result = FundamentalAssessmentEngine.assess(metrics(earningsDateUtc = imminent), now)
        assertEquals("IMMINENT", result.earningsRiskStatus)
        assertTrue("earnings_imminent" in result.reasons)
        assertTrue(result.score in 0.0..100.0)
    }

    @Test
    fun staleFundamentalsAreExplicitlyClassified() {
        val result = FundamentalAssessmentEngine.assess(metrics(dataAgeDays = 240L), now)
        assertEquals("STALE", result.status)
        assertTrue("fundamental_data_stale" in result.reasons)
    }

    @Test
    fun emptyMetricsDoNotInventNeutralCoverage() {
        val empty = FundamentalMetrics(null, null, null, null, null, null, null, null, null)
        val result = FundamentalAssessmentEngine.assess(empty, now)
        assertEquals("EMPTY", result.status)
        assertEquals(0.0, result.coveragePct, 0.001)
        assertEquals(50.0, result.score, 0.001)
    }
}
