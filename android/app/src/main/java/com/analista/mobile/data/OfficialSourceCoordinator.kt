package com.analista.mobile.data

import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import java.time.Instant
import java.time.ZoneOffset

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

    data class InsiderRefreshResult(
        val requestedTickers: Int,
        val mappedTickers: Int,
        val completeTickers: Int,
        val partialTickers: Int,
        val emptyTickers: Int,
        val failedTickers: Int,
        val transactionCount: Int,
        val status: String,
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

    suspend fun refreshInsiders(
        tickers: List<String>,
        maxTickers: Int = 8,
        maxFilingsPerTicker: Int = 2,
        lookbackDays: Long = 35L,
        nowUtc: Long = System.currentTimeMillis()
    ): InsiderRefreshResult {
        require(maxTickers in 1..20)
        require(maxFilingsPerTicker in 1..5)
        require(lookbackDays in 1L..180L)
        val requested = tickers.map(::normalizeTicker).filter(String::isNotBlank).distinct().take(maxTickers)
        if (requested.isEmpty()) return InsiderRefreshResult(0, 0, 0, 0, 0, 0, 0, "EMPTY", nowUtc)
        val email = settingsStore.load().secContactEmail
        if (email.isNullOrBlank()) {
            requested.forEach { ticker ->
                InsiderTransactionRegistry.record(
                    InsiderTransactionRegistry.Snapshot(ticker, emptyList(), "UNKNOWN", nowUtc)
                )
            }
            SourceStatusRegistry.record(
                SourceStatus("INSIDER_SCAN_SEC", "SEC_EDGAR", "NOT_CONFIGURED", "UNKNOWN", nowUtc)
            )
            return InsiderRefreshResult(requested.size, 0, 0, 0, 0, requested.size, 0, "NOT_CONFIGURED", nowUtc)
        }

        val client = SecEdgarClient("Analista Android $email")
        val cutoff = Instant.ofEpochMilli(nowUtc).atZone(ZoneOffset.UTC).toLocalDate().minusDays(lookbackDays)
        var mapped = 0
        var complete = 0
        var partial = 0
        var empty = 0
        var failed = 0
        var transactions = 0

        requested.forEach { ticker ->
            val mapping = OfficialContextRegistry.secTicker(ticker)
            if (mapping == null) {
                failed += 1
                InsiderTransactionRegistry.record(
                    InsiderTransactionRegistry.Snapshot(ticker, emptyList(), "UNAVAILABLE", nowUtc)
                )
                return@forEach
            }
            mapped += 1
            runCatching {
                val filings = client.recentInsiderFilings(mapping.cik, nowUtc)
                    .asSequence()
                    .filter { it.form in setOf("4", "4/A") }
                    .filter { filing ->
                        val date = filing.filingDate ?: filing.reportDate
                        date != null && !date.isBefore(cutoff)
                    }
                    .sortedByDescending { it.filingDate ?: it.reportDate }
                    .take(maxFilingsPerTicker)
                    .toList()
                if (filings.isEmpty()) {
                    InsiderTransactionRegistry.record(
                        InsiderTransactionRegistry.Snapshot(ticker, emptyList(), "EMPTY", nowUtc)
                    )
                    empty += 1
                    return@runCatching
                }
                var filingFailures = 0
                val rows = filings.flatMap { filing ->
                    runCatching { client.insiderTransactions(mapping.cik, filing, nowUtc) }
                        .onFailure { filingFailures += 1 }
                        .getOrElse { emptyList() }
                }
                val status = when {
                    rows.isEmpty() && filingFailures > 0 -> "ERROR"
                    rows.isEmpty() -> "EMPTY"
                    filingFailures > 0 || rows.any { it.transactionCode == null || it.shares == null } -> "PARTIAL"
                    else -> "COMPLETE"
                }
                InsiderTransactionRegistry.record(
                    InsiderTransactionRegistry.Snapshot(ticker, rows, status, nowUtc)
                )
                transactions += rows.size
                when (status) {
                    "COMPLETE" -> complete += 1
                    "PARTIAL" -> partial += 1
                    "EMPTY" -> empty += 1
                    else -> failed += 1
                }
            }.onFailure {
                failed += 1
                InsiderTransactionRegistry.record(
                    InsiderTransactionRegistry.Snapshot(ticker, emptyList(), "ERROR", nowUtc)
                )
            }
        }

        val status = when {
            complete + partial == requested.size -> "AVAILABLE"
            complete + partial > 0 -> "PARTIAL"
            empty > 0 && failed == 0 -> "EMPTY"
            else -> "UNAVAILABLE"
        }
        SourceStatusRegistry.record(
            SourceStatus(
                module = "INSIDER_SCAN_SEC",
                provider = "SEC_EDGAR",
                status = status,
                coverage = when {
                    complete == requested.size -> "COMPLETE"
                    complete + partial > 0 -> "PARTIAL"
                    else -> "EMPTY"
                },
                capturedAtUtc = nowUtc,
                detail = "requested=${requested.size};mapped=$mapped;transactions=$transactions;failed=$failed"
            )
        )
        return InsiderRefreshResult(
            requestedTickers = requested.size,
            mappedTickers = mapped,
            completeTickers = complete,
            partialTickers = partial,
            emptyTickers = empty,
            failedTickers = failed,
            transactionCount = transactions,
            status = status,
            refreshedAtUtc = nowUtc
        )
    }

    fun loadSettings(): OfficialSourceSettingsStore.Settings = settingsStore.load()
    fun saveFredApiKey(value: String) = settingsStore.saveFredApiKey(value)
    fun saveSecContactEmail(value: String) = settingsStore.saveSecContactEmail(value)
    fun clearFredApiKey() = settingsStore.clearFredApiKey()
    fun clearSecContactEmail() = settingsStore.clearSecContactEmail()

    private fun normalizeTicker(value: String): String = value.trim().uppercase().replace('.', '-')
}
