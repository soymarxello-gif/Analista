package com.analista.mobile.data

import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope

class OfficialSourceCoordinator(
    private val settingsStore: OfficialSourceSettingsStore,
    private val fredClient: FredClient = FredClient(),
    private val cboeClient: CboeMarketStatisticsClient = CboeMarketStatisticsClient(),
    private val cftcClient: CftcCotClient = CftcCotClient()
) {
    data class Result(
        val fredSeriesCount: Int,
        val cboeAvailable: Boolean,
        val cftcMarketsCount: Int,
        val secTickerCount: Int,
        val statuses: List<SourceStatus>,
        val refreshedAtUtc: Long
    )

    suspend fun refresh(nowUtc: Long = System.currentTimeMillis()): Result = coroutineScope {
        val settings = settingsStore.load()
        val cboeDeferred = async { runCatching { cboeClient.currentRatios(nowUtc) } }
        val cftcDeferred = async { runCatching { cftcClient.latest(limit = 2_000, nowUtc = nowUtc) } }
        val fredDeferred = async {
            val apiKey = settings.fredApiKey
            if (apiKey.isNullOrBlank()) {
                SourceStatusRegistry.record(SourceStatus("MACRO_FRED", "FRED", "NOT_CONFIGURED", "UNKNOWN", nowUtc))
                emptyList()
            } else {
                FredClient.DEFAULT_SERIES.mapNotNull { seriesId ->
                    runCatching { fredClient.series(seriesId, apiKey, nowUtc = nowUtc) }.getOrNull()
                }
            }
        }
        val secDeferred = async {
            val email = settings.secContactEmail
            if (email.isNullOrBlank()) {
                SourceStatusRegistry.record(SourceStatus("SEC_TICKER_MAP", "SEC_EDGAR", "NOT_CONFIGURED", "UNKNOWN", nowUtc))
                emptyList()
            } else {
                runCatching { SecEdgarClient("Analista Android $email").tickerMap(nowUtc) }.getOrElse { emptyList() }
            }
        }

        val cboe = cboeDeferred.await().getOrNull()
        val cftc = cftcDeferred.await().getOrElse { emptyList() }
        val fred = fredDeferred.await()
        val sec = secDeferred.await()
        cboe?.let(OfficialContextRegistry::recordCboe)
        OfficialContextRegistry.recordCftc(cftc)
        fred.forEach(OfficialContextRegistry::recordFred)
        OfficialContextRegistry.recordSecTickers(sec)
        Result(
            fredSeriesCount = fred.size,
            cboeAvailable = cboe?.coverageCount?.let { it > 0 } == true,
            cftcMarketsCount = cftc.size,
            secTickerCount = sec.size,
            statuses = SourceStatusRegistry.snapshot(),
            refreshedAtUtc = nowUtc
        )
    }

    fun loadSettings(): OfficialSourceSettingsStore.Settings = settingsStore.load()
    fun saveFredApiKey(value: String) = settingsStore.saveFredApiKey(value)
    fun saveSecContactEmail(value: String) = settingsStore.saveSecContactEmail(value)
    fun clearFredApiKey() = settingsStore.clearFredApiKey()
    fun clearSecContactEmail() = settingsStore.clearSecContactEmail()
}
