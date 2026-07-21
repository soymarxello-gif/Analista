package com.analista.mobile.domain

import com.analista.mobile.data.AlpacaMarketDataClient
import com.analista.mobile.data.NasdaqScreenerClient
import com.analista.mobile.data.PriceBar

object DynamicUniverseEngine {
    const val VERSION = "dynamic-universe-1"

    data class Selection(
        val symbol: String,
        val marketCap: Long,
        val sector: String?,
        val industry: String?,
        val averageDollarVolume20: Double,
        val latestPrice: Double,
        val exchange: String?
    )

    fun select(
        assets: List<AlpacaMarketDataClient.AlpacaAsset>,
        metadata: List<NasdaqScreenerClient.StockMetadata>,
        histories: Map<String, List<PriceBar>>,
        maximumSymbols: Int = 80,
        maximumPerSector: Int = 20
    ): List<Selection> {
        require(maximumSymbols > 0)
        require(maximumPerSector > 0)
        val metadataBySymbol = metadata.associateBy { it.symbol }
        val eligible = assets.asSequence()
            .filter { it.tradable && it.status == "active" && it.assetClass == "us_equity" }
            .filter { asset -> asset.exchange?.let { it in ALLOWED_EXCHANGES } == true }
            .mapNotNull { asset ->
                val info = metadataBySymbol[asset.symbol] ?: return@mapNotNull null
                val cap = info.marketCap ?: return@mapNotNull null
                if (cap < TradingPolicy.MIN_MARKET_CAP || excludedName(info.name)) return@mapNotNull null
                val bars = histories[asset.symbol].orEmpty()
                if (bars.size < MIN_BARS) return@mapNotNull null
                val recent = bars.takeLast(20)
                val price = bars.last().close
                val adv = recent.map { it.close * it.volume }.average()
                if (price < TradingPolicy.MIN_PRICE || adv < MIN_DOLLAR_VOLUME) return@mapNotNull null
                Selection(
                    symbol = asset.symbol,
                    marketCap = cap,
                    sector = info.sector,
                    industry = info.industry,
                    averageDollarVolume20 = adv,
                    latestPrice = price,
                    exchange = asset.exchange
                )
            }
            .sortedWith(compareByDescending<Selection> { it.averageDollarVolume20 }.thenByDescending { it.marketCap })
            .toList()

        val selected = mutableListOf<Selection>()
        val sectorCounts = mutableMapOf<String, Int>()
        for (candidate in eligible) {
            val sector = candidate.sector?.trim()?.uppercase().orEmpty().ifBlank { "UNKNOWN" }
            if (sectorCounts.getOrDefault(sector, 0) >= maximumPerSector) continue
            selected += candidate
            sectorCounts[sector] = sectorCounts.getOrDefault(sector, 0) + 1
            if (selected.size >= maximumSymbols) break
        }
        return selected
    }

    private fun excludedName(name: String?): Boolean {
        val normalized = name?.uppercase().orEmpty()
        return EXCLUDED_NAME_TOKENS.any { token -> normalized.contains(token) }
    }

    private val ALLOWED_EXCHANGES = setOf("NASDAQ", "NYSE", "AMEX", "ARCA", "NYSEARCA")
    private val EXCLUDED_NAME_TOKENS = setOf(" ETF", " ETN", " FUND", " WARRANT", " RIGHTS", " UNIT")
    private const val MIN_BARS = 220
    private const val MIN_DOLLAR_VOLUME = 20_000_000.0
}
