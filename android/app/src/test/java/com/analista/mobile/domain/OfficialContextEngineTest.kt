package com.analista.mobile.domain

import com.analista.mobile.data.CboeMarketStatisticsClient
import com.analista.mobile.data.CftcCotClient
import com.analista.mobile.data.FredClient
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

class OfficialContextEngineTest {
    private fun series(id: String, values: List<Double>) = FredClient.Series(
        seriesId = id,
        observations = values.mapIndexed { index, value ->
            FredClient.Observation(LocalDate.of(2025, 1, 1).plusDays(index.toLong()), value)
        },
        capturedAtUtc = 1_700_000_000_000L
    )

    @Test
    fun expandingLiquidityAndModerateInflationSupportMacroContext() {
        val fred = mapOf(
            "DGS10" to series("DGS10", List(25) { 4.2 - it * 0.02 }),
            "DGS30" to series("DGS30", List(25) { 4.5 - it * 0.015 }),
            "T10Y2Y" to series("T10Y2Y", listOf(0.1, 0.2)),
            "WALCL" to series("WALCL", List(15) { 8_000.0 + it * 10.0 }),
            "RRPONTSYD" to series("RRPONTSYD", List(22) { 500.0 - it * 10.0 }),
            "M2SL" to series("M2SL", List(8) { 21_000.0 + it * 50.0 }),
            "CPIAUCSL" to series("CPIAUCSL", List(14) { 300.0 + it * 0.5 }),
            "UNRATE" to series("UNRATE", listOf(4.1, 4.0, 3.9, 3.8))
        )

        val result = OfficialContextEngine.assessMacro(fred)

        assertEquals("EXPANDING", result.liquidityRegime)
        assertEquals("FALLING", result.ratesRegime)
        assertEquals("IMPROVING", result.laborRegime)
        assertTrue(result.scoreAdjustment > 0.0)
        assertEquals(100.0, result.coveragePct, 0.0)
    }

    @Test
    fun contractingLiquidityAndHighInflationReduceMacroScore() {
        val fred = mapOf(
            "DGS10" to series("DGS10", List(25) { 3.5 + it * 0.03 }),
            "DGS30" to series("DGS30", List(25) { 3.8 + it * 0.03 }),
            "T10Y2Y" to series("T10Y2Y", listOf(-0.2, -0.3)),
            "WALCL" to series("WALCL", List(15) { 8_200.0 - it * 15.0 }),
            "RRPONTSYD" to series("RRPONTSYD", List(22) { 100.0 + it * 15.0 }),
            "M2SL" to series("M2SL", List(8) { 21_000.0 - it * 60.0 }),
            "CPIAUCSL" to series("CPIAUCSL", List(14) { 280.0 + it * 1.5 }),
            "UNRATE" to series("UNRATE", listOf(3.8, 3.9, 4.0, 4.3))
        )

        val result = OfficialContextEngine.assessMacro(fred)

        assertEquals("CONTRACTING", result.liquidityRegime)
        assertEquals("RISING", result.ratesRegime)
        assertEquals("WEAKENING", result.laborRegime)
        assertTrue(result.scoreAdjustment < 0.0)
        assertTrue("fred_liquidity_contracting" in result.reasons)
    }

    @Test
    fun cboeAndCftcProduceExplicitInstitutionalContext() {
        val cboe = CboeMarketStatisticsClient.Ratios(
            totalPutCall = 0.65,
            indexPutCall = 0.9,
            equityPutCall = 0.50,
            vixPutCall = null,
            spxPutCall = 0.8,
            capturedAtUtc = 1L
        )
        val cftc = listOf(
            CftcCotClient.Positioning("E-MINI S&P 500", LocalDate.of(2026, 7, 14), 150, 50, 120, 80, null, null),
            CftcCotClient.Positioning("NASDAQ-100", LocalDate.of(2026, 7, 14), 140, 60, 110, 90, null, null),
            CftcCotClient.Positioning("RUSSELL 2000", LocalDate.of(2026, 7, 14), 130, 70, 105, 95, null, null)
        )

        val result = OfficialContextEngine.assessInstitutional(cboe, cftc)

        assertEquals("CROWDED_BULLISH", result.marketOptionsRegime)
        assertEquals(-5.0, result.marketOptionsAdjustment, 0.0)
        assertEquals("COMPLETE", result.futuresStatus)
        assertTrue((result.futuresScore ?: 0.0) > 50.0)
    }

    @Test
    fun unavailableOfficialDataRemainsUnknown() {
        val result = OfficialContextEngine.assess(emptyMap(), null, emptyList())

        assertEquals("UNKNOWN", result.macro.liquidityRegime)
        assertEquals("UNKNOWN", result.institutional.marketOptionsRegime)
        assertEquals("UNKNOWN", result.institutional.futuresStatus)
        assertTrue(result.institutional.futuresScore == null)
    }
}
