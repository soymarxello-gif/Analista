package com.analista.mobile.data

import com.analista.mobile.domain.UsMarketSessionClock

class MarketDataGateway(
    private val yahoo: YahooFinanceClient,
    private val alpaca: AlpacaMarketDataClient,
    private val credentialsStore: AlpacaCredentialsStore
) {
    data class BatchQuoteResult(
        val quotes: Map<String, MarketQuote>,
        val primarySource: String,
        val feed: String?,
        val alpacaStatus: String,
        val fallbackCount: Int,
        val divergenceCount: Int
    )

    data class AssetCatalogResult(
        val assets: List<AlpacaMarketDataClient.AlpacaAsset>,
        val source: String,
        val status: String,
        val feed: String?
    )

    data class HistoryBatchResult(
        val histories: Map<String, FetchResult>,
        val primarySource: String,
        val feed: String?,
        val alpacaStatus: String,
        val fallbackCount: Int,
        val failedSymbols: List<String>
    )

    suspend fun quotes(symbols: List<String>): BatchQuoteResult {
        val credentials = credentialsStore.load()
        if (credentials == null) {
            val yahooQuotes = yahooQuotes(symbols)
            return BatchQuoteResult(yahooQuotes, "Yahoo Finance", null, "NOT_CONFIGURED", yahooQuotes.size, 0)
        }

        val alpacaResult = runCatching { alpaca.latestQuotes(symbols, credentials) }
        val alpacaQuotes = alpacaResult.getOrNull().orEmpty()
        val status = alpacaStatus(alpacaResult.exceptionOrNull(), alpacaQuotes.isEmpty())

        val results = mutableMapOf<String, MarketQuote>()
        var fallbackCount = 0
        var divergenceCount = 0
        for (symbol in normalizeSymbols(symbols)) {
            val metadata = SecurityMetadataRegistry.get(symbol)
            val alpacaQuote = alpacaQuotes[symbol]
            val usableAlpaca = alpacaQuote?.bid != null && alpacaQuote.ask != null && alpacaQuote.ask > alpacaQuote.bid
            val yahooQuote = when {
                !usableAlpaca -> runCatching { yahoo.marketQuote(symbol) }.getOrNull()
                metadata == null -> runCatching { yahoo.marketQuote(symbol) }.getOrNull()
                else -> null
            }
            if (usableAlpaca) {
                val yahooMid = yahooQuote?.let { q ->
                    val bid = q.bid
                    val ask = q.ask
                    if (bid != null && ask != null && ask > bid) (bid + ask) / 2.0 else q.preMarketPrice ?: q.regularMarketPrice
                }
                val alpacaMid = (alpacaQuote.bid!! + alpacaQuote.ask!!) / 2.0
                if (yahooMid != null && kotlin.math.abs(alpacaMid / yahooMid - 1.0) * 100.0 > MAX_DIVERGENCE_PCT) {
                    divergenceCount += 1
                }
                val retrievedAtUtc = System.currentTimeMillis()
                val providerTimestamp = alpacaQuote.timestampUtcMillis
                results[symbol] = MarketQuote(
                    bid = alpacaQuote.bid,
                    ask = alpacaQuote.ask,
                    regularMarketPrice = yahooQuote?.regularMarketPrice,
                    preMarketPrice = alpacaMid,
                    marketCap = metadata?.marketCap ?: yahooQuote?.marketCap,
                    quoteType = metadata?.quoteType ?: yahooQuote?.quoteType,
                    marketState = yahooQuote?.marketState ?: UsMarketSessionClock.marketState(retrievedAtUtc),
                    capturedAtUtc = providerTimestamp ?: retrievedAtUtc,
                    providerTimestampUtc = providerTimestamp,
                    retrievedAtUtc = retrievedAtUtc,
                    provider = "ALPACA/${credentials.feed}"
                )
            } else if (yahooQuote != null) {
                fallbackCount += 1
                results[symbol] = yahooQuote.copy(
                    marketCap = metadata?.marketCap ?: yahooQuote.marketCap,
                    quoteType = metadata?.quoteType ?: yahooQuote.quoteType
                )
            }
        }
        return BatchQuoteResult(
            quotes = results,
            primarySource = if (alpacaQuotes.isNotEmpty()) "Alpaca ${credentials.feed}" else "Yahoo Finance",
            feed = credentials.feed,
            alpacaStatus = status,
            fallbackCount = fallbackCount,
            divergenceCount = divergenceCount
        )
    }

    suspend fun activeAssetCatalog(): AssetCatalogResult {
        val credentials = credentialsStore.load()
            ?: return AssetCatalogResult(emptyList(), "NONE", "NOT_CONFIGURED", null)
        val result = runCatching { alpaca.activeUsEquities(credentials) }
        val assets = result.getOrNull().orEmpty()
        return AssetCatalogResult(
            assets = assets,
            source = if (assets.isEmpty()) "NONE" else "ALPACA_ASSETS",
            status = alpacaStatus(result.exceptionOrNull(), assets.isEmpty()),
            feed = credentials.feed
        )
    }

    suspend fun dailyHistories(symbols: List<String>, yahooRange: String = "2y"): HistoryBatchResult {
        val normalized = normalizeSymbols(symbols)
        val credentials = credentialsStore.load()
        val alpacaResult: Result<Map<String, List<PriceBar>>> = if (credentials != null) {
            runCatching { alpaca.dailyBars(normalized, credentials) }
        } else {
            Result.success(emptyMap())
        }
        val alpacaBars = alpacaResult.getOrNull().orEmpty()
        val histories = mutableMapOf<String, FetchResult>()
        alpacaBars.forEach { (symbol, bars) ->
            if (bars.size >= MIN_HISTORY_BARS) {
                histories[symbol] = FetchResult(
                    bars = bars,
                    source = "Alpaca/${credentials?.feed ?: "unknown"}",
                    cacheHit = false,
                    retries = 0
                )
            }
        }

        var fallbackCount = 0
        val failed = mutableListOf<String>()
        val missing = normalized.filterNot { it in histories }
        val yahooFallbackSymbols = if (normalized.size <= MAX_BULK_YAHOO_FALLBACK) missing else emptyList()
        yahooFallbackSymbols.forEach { symbol ->
            val fallback = runCatching { yahoo.dailyHistory(symbol, yahooRange) }.getOrNull()
            if (fallback != null) {
                histories[symbol] = fallback
                fallbackCount += 1
            } else {
                failed += symbol
            }
        }
        failed += missing.filterNot { it in yahooFallbackSymbols }
        val primarySource = when {
            histories.isEmpty() -> "UNAVAILABLE"
            alpacaBars.isNotEmpty() && fallbackCount > 0 -> "ALPACA_BARS+YAHOO_FALLBACK"
            alpacaBars.isNotEmpty() -> "ALPACA_BARS"
            else -> "YAHOO_BARS"
        }
        return HistoryBatchResult(
            histories = histories,
            primarySource = primarySource,
            feed = credentials?.feed,
            alpacaStatus = when {
                credentials == null -> "NOT_CONFIGURED"
                else -> alpacaStatus(alpacaResult.exceptionOrNull(), alpacaBars.isEmpty())
            },
            fallbackCount = fallbackCount,
            failedSymbols = failed
        )
    }

    suspend fun testAlpacaConnection(credentials: AlpacaCredentialsStore.Credentials) = alpaca.testConnection(credentials)

    fun saveAlpacaCredentials(credentials: AlpacaCredentialsStore.Credentials) = credentialsStore.save(credentials)
    fun clearAlpacaCredentials() = credentialsStore.clear()
    fun alpacaCredentials(): AlpacaCredentialsStore.Credentials? = credentialsStore.load()

    private suspend fun yahooQuotes(symbols: List<String>): Map<String, MarketQuote> = buildMap {
        for (symbol in normalizeSymbols(symbols)) runCatching { yahoo.marketQuote(symbol) }.getOrNull()?.let { quote ->
            val metadata = SecurityMetadataRegistry.get(symbol)
            put(
                symbol,
                quote.copy(
                    marketCap = metadata?.marketCap ?: quote.marketCap,
                    quoteType = metadata?.quoteType ?: quote.quoteType
                )
            )
        }
    }

    private fun normalizeSymbols(symbols: List<String>): List<String> = symbols.asSequence()
        .map { it.trim().uppercase().replace('.', '-') }
        .filter { it.isNotBlank() }
        .distinct()
        .toList()

    private fun alpacaStatus(error: Throwable?, empty: Boolean): String = when (error) {
        null -> if (empty) "EMPTY" else "AVAILABLE"
        is AlpacaMarketDataClient.AlpacaException -> error.status
        else -> "NETWORK_ERROR"
    }

    companion object {
        private const val MAX_DIVERGENCE_PCT = 1.0
        private const val MIN_HISTORY_BARS = 220
        private const val MAX_BULK_YAHOO_FALLBACK = 100
    }
}
