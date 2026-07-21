package com.analista.mobile.data

import java.util.concurrent.ConcurrentHashMap

object OfficialContextRegistry {
    const val VERSION = "official-context-1"

    private val fred = ConcurrentHashMap<String, FredClient.Series>()
    @Volatile private var cboe: CboeMarketStatisticsClient.Ratios? = null
    @Volatile private var cftc: List<CftcCotClient.Positioning> = emptyList()
    @Volatile private var secTickers: List<SecEdgarClient.TickerCik> = emptyList()

    fun recordFred(series: FredClient.Series) { fred[series.seriesId] = series }
    fun fred(seriesId: String): FredClient.Series? = fred[seriesId.trim().uppercase()]
    fun fredSnapshot(): Map<String, FredClient.Series> = fred.toSortedMap()

    fun recordCboe(value: CboeMarketStatisticsClient.Ratios) { cboe = value }
    fun cboe(): CboeMarketStatisticsClient.Ratios? = cboe

    fun recordCftc(values: List<CftcCotClient.Positioning>) { cftc = values.toList() }
    fun cftc(): List<CftcCotClient.Positioning> = cftc

    fun recordSecTickers(values: List<SecEdgarClient.TickerCik>) { secTickers = values.toList() }
    fun secTicker(ticker: String): SecEdgarClient.TickerCik? = secTickers.firstOrNull {
        it.ticker == ticker.trim().uppercase()
    }

    fun clear() {
        fred.clear()
        cboe = null
        cftc = emptyList()
        secTickers = emptyList()
    }
}
