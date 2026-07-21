package com.analista.mobile.data

import com.analista.mobile.domain.DynamicUniverseEngine
import com.analista.mobile.domain.TradingPolicy
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope

class DynamicUniverseResolver(
    private val marketData: MarketDataGateway,
    private val nasdaq: NasdaqScreenerClient,
    private val store: DynamicUniverseStore
) {
    data class Resolution(
        val symbols: List<String>,
        val histories: Map<String, FetchResult>,
        val source: String,
        val status: String,
        val fallbackUsed: Boolean,
        val catalogStatus: String,
        val historyStatus: String
    )

    suspend fun resolve(emergencySymbols: List<String>, nowUtc: Long = System.currentTimeMillis()): Resolution = coroutineScope {
        val catalogDeferred = async { marketData.activeAssetCatalog() }
        val metadataDeferred = async { runCatching { nasdaq.stocks() } }
        val catalog = catalogDeferred.await()
        val metadataResult = metadataDeferred.await()
        val metadata = metadataResult.getOrNull().orEmpty()

        if (catalog.assets.isNotEmpty() && metadata.isNotEmpty()) {
            val metadataBySymbol = metadata.associateBy { it.symbol }
            val preliminary = catalog.assets.asSequence()
                .filter { it.tradable && it.status == "active" && it.assetClass == "us_equity" }
                .mapNotNull { asset ->
                    val info = metadataBySymbol[asset.symbol] ?: return@mapNotNull null
                    val cap = info.marketCap ?: return@mapNotNull null
                    if (cap < TradingPolicy.MIN_MARKET_CAP) return@mapNotNull null
                    asset.symbol to cap
                }
                .sortedByDescending { it.second }
                .take(PRELIMINARY_LIMIT)
                .map { it.first }
                .toList()
            if (preliminary.isNotEmpty()) {
                val historyBatch = marketData.dailyHistories(preliminary)
                val selected = DynamicUniverseEngine.select(
                    assets = catalog.assets,
                    metadata = metadata,
                    histories = historyBatch.histories.mapValues { it.value.bars },
                    maximumSymbols = MAXIMUM_SYMBOLS,
                    maximumPerSector = MAXIMUM_PER_SECTOR
                )
                if (selected.size >= MINIMUM_DYNAMIC_SYMBOLS) {
                    val members = selected.map {
                        DynamicUniverseStore.Member(it.symbol, it.marketCap, it.sector, it.industry)
                    }
                    store.save(DynamicUniverseStore.Snapshot(members, LIVE_SOURCE, nowUtc))
                    recordMetadata(members, LIVE_SOURCE, nowUtc)
                    val symbols = members.map { it.symbol }
                    return@coroutineScope Resolution(
                        symbols = symbols,
                        histories = historyBatch.histories.filterKeys { it in symbols },
                        source = LIVE_SOURCE,
                        status = "LIVE",
                        fallbackUsed = historyBatch.fallbackCount > 0,
                        catalogStatus = catalog.status,
                        historyStatus = historyBatch.primarySource
                    )
                }
            }
        }

        val cached = store.load(nowUtc)
        if (cached != null) {
            recordMetadata(cached.members, "LAST_GOOD_DYNAMIC", cached.createdAtUtc)
            val historyBatch = marketData.dailyHistories(cached.symbols)
            val usable = cached.symbols.filter { historyBatch.histories[it]?.bars?.size ?: 0 >= MINIMUM_HISTORY_BARS }
            if (usable.size >= MINIMUM_FALLBACK_SYMBOLS) {
                return@coroutineScope Resolution(
                    symbols = usable,
                    histories = historyBatch.histories.filterKeys { it in usable },
                    source = "LAST_GOOD_DYNAMIC",
                    status = "STALE_FALLBACK",
                    fallbackUsed = true,
                    catalogStatus = catalog.status,
                    historyStatus = historyBatch.primarySource
                )
            }
        }

        val emergency = emergencySymbols.map { it.trim().uppercase().replace('.', '-') }.filter { it.isNotBlank() }.distinct()
        val emergencyHistory = marketData.dailyHistories(emergency)
        Resolution(
            symbols = emergency.filter { it in emergencyHistory.histories },
            histories = emergencyHistory.histories,
            source = "EMERGENCY_STATIC",
            status = "DEGRADED_STATIC_FALLBACK",
            fallbackUsed = true,
            catalogStatus = catalog.status,
            historyStatus = emergencyHistory.primarySource
        )
    }

    private fun recordMetadata(members: List<DynamicUniverseStore.Member>, source: String, capturedAtUtc: Long) {
        SecurityMetadataRegistry.recordAll(
            members.map {
                SecurityMetadataRegistry.Metadata(
                    ticker = it.symbol,
                    marketCap = it.marketCap,
                    quoteType = "EQUITY",
                    sector = it.sector,
                    industry = it.industry,
                    source = source,
                    capturedAtUtc = capturedAtUtc
                )
            }
        )
    }

    companion object {
        const val LIVE_SOURCE = "ALPACA_ASSETS+NASDAQ_METADATA+ALPACA_BARS"
        private const val PRELIMINARY_LIMIT = 350
        private const val MAXIMUM_SYMBOLS = 80
        private const val MAXIMUM_PER_SECTOR = 20
        private const val MINIMUM_DYNAMIC_SYMBOLS = 20
        private const val MINIMUM_FALLBACK_SYMBOLS = 10
        private const val MINIMUM_HISTORY_BARS = 220
    }
}
