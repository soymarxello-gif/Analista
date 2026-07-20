package com.analista.mobile.data

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

    suspend fun quotes(symbols: List<String>): BatchQuoteResult {
        val credentials = credentialsStore.load()
        if (credentials == null) {
            val yahooQuotes = yahooQuotes(symbols)
            return BatchQuoteResult(yahooQuotes, "Yahoo Finance", null, "NOT_CONFIGURED", yahooQuotes.size, 0)
        }

        val alpacaResult = runCatching { alpaca.latestQuotes(symbols, credentials) }
        val alpacaQuotes = alpacaResult.getOrNull().orEmpty()
        val status = when (val error = alpacaResult.exceptionOrNull()) {
            null -> if (alpacaQuotes.isEmpty()) "EMPTY" else "AVAILABLE"
            is AlpacaMarketDataClient.AlpacaException -> error.status
            else -> "NETWORK_ERROR"
        }

        val results = mutableMapOf<String, MarketQuote>()
        var fallbackCount = 0
        var divergenceCount = 0
        for (symbol in symbols.distinct()) {
            val yahooQuote = runCatching { yahoo.marketQuote(symbol) }.getOrNull()
            val alpacaQuote = alpacaQuotes[symbol.uppercase()]
            val usableAlpaca = alpacaQuote?.bid != null && alpacaQuote.ask != null && alpacaQuote.ask > alpacaQuote.bid
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
                    marketCap = yahooQuote?.marketCap,
                    quoteType = yahooQuote?.quoteType,
                    marketState = yahooQuote?.marketState,
                    capturedAtUtc = providerTimestamp ?: retrievedAtUtc,
                    providerTimestampUtc = providerTimestamp,
                    retrievedAtUtc = retrievedAtUtc,
                    provider = "ALPACA"
                )
            } else if (yahooQuote != null) {
                fallbackCount += 1
                results[symbol] = yahooQuote
            }
        }
        return BatchQuoteResult(
            quotes = results,
            primarySource = if (alpacaQuotes.isNotEmpty()) "Alpaca + Yahoo metadata" else "Yahoo Finance",
            feed = credentials.feed,
            alpacaStatus = status,
            fallbackCount = fallbackCount,
            divergenceCount = divergenceCount
        )
    }

    suspend fun testAlpacaConnection(credentials: AlpacaCredentialsStore.Credentials) = alpaca.testConnection(credentials)

    fun saveAlpacaCredentials(credentials: AlpacaCredentialsStore.Credentials) = credentialsStore.save(credentials)
    fun clearAlpacaCredentials() = credentialsStore.clear()
    fun alpacaCredentials(): AlpacaCredentialsStore.Credentials? = credentialsStore.load()

    private suspend fun yahooQuotes(symbols: List<String>): Map<String, MarketQuote> = buildMap {
        for (symbol in symbols.distinct()) runCatching { yahoo.marketQuote(symbol) }.getOrNull()?.let { put(symbol, it) }
    }

    companion object { private const val MAX_DIVERGENCE_PCT = 1.0 }
}
