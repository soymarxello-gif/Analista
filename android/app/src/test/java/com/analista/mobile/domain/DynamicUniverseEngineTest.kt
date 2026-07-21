package com.analista.mobile.domain

import com.analista.mobile.data.AlpacaMarketDataClient
import com.analista.mobile.data.NasdaqScreenerClient
import com.analista.mobile.data.PriceBar
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DynamicUniverseEngineTest {
    private fun asset(symbol: String, exchange: String = "NASDAQ") = AlpacaMarketDataClient.AlpacaAsset(
        symbol = symbol,
        name = symbol,
        exchange = exchange,
        assetClass = "us_equity",
        status = "active",
        tradable = true,
        fractionable = true,
        marginable = true,
        shortable = true,
        easyToBorrow = true
    )

    private fun metadata(
        symbol: String,
        cap: Long = 5_000_000_000L,
        sector: String = "Technology",
        name: String = "$symbol Inc."
    ) = NasdaqScreenerClient.StockMetadata(symbol, name, cap, "United States", sector, "Software")

    private fun bars(price: Double = 100.0, volume: Long = 1_000_000L): List<PriceBar> =
        (0 until 240).map { index ->
            val close = price + index * 0.01
            PriceBar(index.toLong(), close - 0.5, close + 1.0, close - 1.0, close, volume)
        }

    @Test
    fun selectsOnlyVerifiedLiquidCommonEquities() {
        val result = DynamicUniverseEngine.select(
            assets = listOf(asset("GOOD"), asset("SMALL"), asset("ILLIQUID"), asset("ETF")),
            metadata = listOf(
                metadata("GOOD"),
                metadata("SMALL", cap = 500_000_000L),
                metadata("ILLIQUID"),
                metadata("ETF", name = "Example ETF")
            ),
            histories = mapOf(
                "GOOD" to bars(),
                "SMALL" to bars(),
                "ILLIQUID" to bars(volume = 1_000L),
                "ETF" to bars()
            )
        )
        assertEquals(listOf("GOOD"), result.map { it.symbol })
        assertTrue(result.first().averageDollarVolume20 >= 20_000_000.0)
    }

    @Test
    fun capsSectorConcentration() {
        val symbols = listOf("A", "B", "C", "D")
        val result = DynamicUniverseEngine.select(
            assets = symbols.map { asset(it) },
            metadata = symbols.map { metadata(it, sector = if (it == "D") "Energy" else "Technology") },
            histories = symbols.associateWith { bars(volume = 2_000_000L) },
            maximumSymbols = 4,
            maximumPerSector = 2
        )
        assertEquals(3, result.size)
        assertFalse(result.count { it.sector == "Technology" } > 2)
        assertTrue(result.any { it.sector == "Energy" })
    }
}
