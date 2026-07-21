package com.analista.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import java.time.LocalDate

class OfficialContextRegistryTest {
    @Before
    fun clear() {
        OfficialContextRegistry.clear()
        SourceStatusRegistry.clear()
    }

    @Test
    fun storesMacroOptionsFuturesAndSecContextWithoutInventingFallbacks() {
        val fred = FredClient.Series(
            seriesId = "DGS10",
            observations = listOf(FredClient.Observation(LocalDate.of(2026, 7, 20), 4.25)),
            capturedAtUtc = 100L
        )
        OfficialContextRegistry.recordFred(fred)
        OfficialContextRegistry.recordCboe(
            CboeMarketStatisticsClient.Ratios(1.0, 1.1, 0.7, 0.6, 1.2, 100L)
        )
        OfficialContextRegistry.recordCftc(
            listOf(CftcCotClient.Positioning("E-MINI S&P 500", LocalDate.of(2026, 7, 14), 100L, 50L, 30L, 60L, 20L, 25L))
        )
        OfficialContextRegistry.recordSecTickers(listOf(SecEdgarClient.TickerCik("META", "0001326801", "Meta")))

        assertEquals(4.25, OfficialContextRegistry.fred("dgs10")?.observations?.single()?.value ?: 0.0, 0.0)
        assertEquals(0.7, OfficialContextRegistry.cboe()?.equityPutCall ?: 0.0, 0.0)
        assertEquals(-30L, OfficialContextRegistry.cftc().single().leveragedFundsNet)
        assertEquals("0001326801", OfficialContextRegistry.secTicker("meta")?.cik)
        assertNull(OfficialContextRegistry.fred("UNKNOWN"))
    }
}
