package com.analista.mobile.data

import android.content.Context
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.kotlin.mock
import java.time.Instant

class YahooTemporalFundamentalsTest {
    private val client = YahooFinanceClient(mock<Context>())

    @Test
    fun parsesQuarterlyGrowthMarginsLeverageCashFlowAndEarnings() {
        val json = """{
          "quoteSummary": {
            "result": [{
              "summaryDetail": {
                "marketCap": {"raw": 100000000000},
                "trailingPE": {"raw": 25.0},
                "priceToSalesTrailing12Months": {"raw": 4.0}
              },
              "defaultKeyStatistics": {"trailingEps": {"raw": 5.0}},
              "financialData": {
                "revenueGrowth": {"raw": 0.18},
                "grossMargins": {"raw": 0.62},
                "operatingMargins": {"raw": 0.28},
                "profitMargins": {"raw": 0.22},
                "debtToEquity": {"raw": 55.0},
                "totalDebt": {"raw": 1800.0},
                "ebitda": {"raw": 1000.0},
                "freeCashflow": {"raw": 500.0}
              },
              "assetProfile": {"sector": "Technology"},
              "incomeStatementHistoryQuarterly": {
                "incomeStatementHistory": [
                  {"endDate":{"raw":1772323200},"totalRevenue":{"raw":1200},"dilutedEPS":{"raw":1.2},"grossProfit":{"raw":744},"operatingIncome":{"raw":336},"netIncome":{"raw":264},"ebit":{"raw":340},"interestExpense":{"raw":34}},
                  {"endDate":{"raw":1764547200},"totalRevenue":{"raw":1100},"dilutedEPS":{"raw":1.1},"grossProfit":{"raw":660},"operatingIncome":{"raw":286},"netIncome":{"raw":220}},
                  {"endDate":{"raw":1756684800},"totalRevenue":{"raw":1080},"dilutedEPS":{"raw":1.08}},
                  {"endDate":{"raw":1748736000},"totalRevenue":{"raw":1040},"dilutedEPS":{"raw":1.04}},
                  {"endDate":{"raw":1740787200},"totalRevenue":{"raw":1000},"dilutedEPS":{"raw":1.0}}
                ]
              },
              "cashflowStatementHistoryQuarterly": {
                "cashflowStatements": [
                  {"endDate":{"raw":1772323200},"totalCashFromOperatingActivities":{"raw":600},"capitalExpenditures":{"raw":-100}}
                ]
              },
              "balanceSheetHistoryQuarterly": {
                "balanceSheetStatements": [
                  {"endDate":{"raw":1772323200},"totalDebt":{"raw":1800}}
                ]
              },
              "calendarEvents": {
                "earnings": {"earningsDate":[{"raw":1784577600}]}
              }
            }],
            "error": null
          }
        }"""
        val now = Instant.parse("2026-07-20T13:00:00Z").toEpochMilli()
        val metrics = client.parseFundamentals(json, "TEST", now)

        assertEquals(20.0, metrics.revenueYoyPct ?: 0.0, 0.001)
        assertEquals(20.0, metrics.epsYoyPct ?: 0.0, 0.001)
        assertEquals("IMPROVING", metrics.revenueTrend)
        assertEquals("IMPROVING", metrics.epsTrend)
        assertEquals(62.0, metrics.grossMarginPct ?: 0.0, 0.001)
        assertEquals(2.0, metrics.grossMarginDeltaPct ?: 0.0, 0.001)
        assertEquals(1.8, metrics.debtToEbitda ?: 0.0, 0.001)
        assertEquals(10.0, metrics.interestCoverage ?: 0.0, 0.001)
        assertEquals(500.0, metrics.freeCashFlow ?: 0.0, 0.001)
        assertEquals("Technology", metrics.sector)
        assertTrue((metrics.dataAgeDays ?: 999L) < 180L)
        assertTrue((metrics.earningsDateUtc ?: 0L) > now)
    }
}
