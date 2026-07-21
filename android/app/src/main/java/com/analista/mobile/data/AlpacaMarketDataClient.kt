package com.analista.mobile.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.time.Instant
import java.time.temporal.ChronoUnit
import java.util.concurrent.TimeUnit

class AlpacaMarketDataClient(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(35, TimeUnit.SECONDS)
        .callTimeout(50, TimeUnit.SECONDS)
        .build()
) {
    data class AlpacaQuote(
        val symbol: String,
        val bid: Double?,
        val ask: Double?,
        val timestampUtcMillis: Long?,
        val feed: String
    )

    data class AlpacaAsset(
        val symbol: String,
        val name: String?,
        val exchange: String?,
        val assetClass: String,
        val status: String,
        val tradable: Boolean,
        val fractionable: Boolean,
        val marginable: Boolean,
        val shortable: Boolean,
        val easyToBorrow: Boolean
    )

    data class BarsPage(
        val bars: Map<String, List<PriceBar>>,
        val nextPageToken: String?
    )

    data class ConnectionResult(val ok: Boolean, val status: String, val message: String)

    suspend fun latestQuotes(
        symbols: List<String>,
        credentials: AlpacaCredentialsStore.Credentials
    ): Map<String, AlpacaQuote> = withContext(Dispatchers.IO) {
        if (symbols.isEmpty()) return@withContext emptyMap()
        val normalized = normalizeSymbols(symbols)
        val url = "$DATA_BASE/v2/stocks/quotes/latest".toHttpUrl().newBuilder()
            .addQueryParameter("symbols", normalized.joinToString(","))
            .addQueryParameter("feed", credentials.feed)
            .build()
        executeJson(url.toString(), credentials).let { parseLatestQuotes(it, credentials.feed) }
    }

    suspend fun activeUsEquities(
        credentials: AlpacaCredentialsStore.Credentials
    ): List<AlpacaAsset> = withContext(Dispatchers.IO) {
        var lastError: Throwable? = null
        for (base in ASSET_BASES) {
            try {
                val url = "$base/v2/assets".toHttpUrl().newBuilder()
                    .addQueryParameter("status", "active")
                    .addQueryParameter("asset_class", "us_equity")
                    .build()
                return@withContext parseAssets(executeJson(url.toString(), credentials))
                    .filter { it.status == "active" && it.assetClass == "us_equity" && it.tradable }
            } catch (error: Throwable) {
                lastError = error
            }
        }
        throw lastError ?: IOException("Alpaca assets unavailable")
    }

    suspend fun dailyBars(
        symbols: List<String>,
        credentials: AlpacaCredentialsStore.Credentials,
        start: Instant = Instant.now().minus(650, ChronoUnit.DAYS),
        end: Instant = Instant.now(),
        batchSize: Int = 100
    ): Map<String, List<PriceBar>> = withContext(Dispatchers.IO) {
        require(batchSize in 1..200)
        val normalized = normalizeSymbols(symbols)
        if (normalized.isEmpty()) return@withContext emptyMap()
        val output = normalized.associateWith { mutableListOf<PriceBar>() }.toMutableMap()
        normalized.chunked(batchSize).forEach { batch ->
            var pageToken: String? = null
            var pages = 0
            do {
                require(pages < MAX_BAR_PAGES) { "Alpaca bars pagination limit exceeded" }
                val builder = "$DATA_BASE/v2/stocks/bars".toHttpUrl().newBuilder()
                    .addQueryParameter("symbols", batch.joinToString(","))
                    .addQueryParameter("timeframe", "1Day")
                    .addQueryParameter("start", start.toString())
                    .addQueryParameter("end", end.toString())
                    .addQueryParameter("limit", "10000")
                    .addQueryParameter("adjustment", "all")
                    .addQueryParameter("feed", credentials.feed)
                    .addQueryParameter("sort", "asc")
                pageToken?.let { builder.addQueryParameter("page_token", it) }
                val page = parseBarsPage(executeJson(builder.build().toString(), credentials))
                page.bars.forEach { (symbol, bars) -> output.getOrPut(symbol) { mutableListOf() }.addAll(bars) }
                pageToken = page.nextPageToken
                pages += 1
            } while (!pageToken.isNullOrBlank())
        }
        output.mapValues { (_, bars) -> bars.distinctBy { it.epochSeconds }.sortedBy { it.epochSeconds } }
            .filterValues { it.isNotEmpty() }
    }

    suspend fun testConnection(credentials: AlpacaCredentialsStore.Credentials): ConnectionResult =
        runCatching { latestQuotes(listOf("SPY"), credentials) }
            .fold(
                onSuccess = { quotes ->
                    if (quotes["SPY"] != null) ConnectionResult(true, "CONNECTED", "Alpaca ${credentials.feed} disponible")
                    else ConnectionResult(false, "EMPTY", "Alpaca respondió sin quote para SPY")
                },
                onFailure = { error ->
                    val status = (error as? AlpacaException)?.status ?: "NETWORK_ERROR"
                    ConnectionResult(false, status, error.message ?: status)
                }
            )

    internal fun parseLatestQuotes(json: String, feed: String): Map<String, AlpacaQuote> {
        val root = JSONObject(json)
        val quotes = root.optJSONObject("quotes") ?: return emptyMap()
        return buildMap {
            val keys = quotes.keys()
            while (keys.hasNext()) {
                val symbol = keys.next().uppercase()
                val value = quotes.optJSONObject(symbol) ?: continue
                put(
                    symbol,
                    AlpacaQuote(
                        symbol = symbol,
                        bid = value.optPositiveDouble("bp"),
                        ask = value.optPositiveDouble("ap"),
                        timestampUtcMillis = value.optString("t").takeIf { it.isNotBlank() }
                            ?.let { runCatching { Instant.parse(it).toEpochMilli() }.getOrNull() },
                        feed = feed
                    )
                )
            }
        }
    }

    internal fun parseAssets(json: String): List<AlpacaAsset> {
        val array = JSONArray(json)
        return buildList {
            for (index in 0 until array.length()) {
                val value = array.optJSONObject(index) ?: continue
                val symbol = value.optString("symbol").trim().uppercase()
                if (symbol.isBlank()) continue
                add(
                    AlpacaAsset(
                        symbol = symbol,
                        name = value.optString("name").trim().takeIf { it.isNotBlank() },
                        exchange = value.optString("exchange").trim().uppercase().takeIf { it.isNotBlank() },
                        assetClass = value.optString("class").trim().lowercase(),
                        status = value.optString("status").trim().lowercase(),
                        tradable = value.optBoolean("tradable", false),
                        fractionable = value.optBoolean("fractionable", false),
                        marginable = value.optBoolean("marginable", false),
                        shortable = value.optBoolean("shortable", false),
                        easyToBorrow = value.optBoolean("easy_to_borrow", false)
                    )
                )
            }
        }
    }

    internal fun parseBarsPage(json: String): BarsPage {
        val root = JSONObject(json)
        val payload = root.optJSONObject("bars") ?: JSONObject()
        val output = buildMap {
            val symbols = payload.keys()
            while (symbols.hasNext()) {
                val symbol = symbols.next().uppercase()
                val array = payload.optJSONArray(symbol) ?: continue
                val bars = buildList {
                    for (index in 0 until array.length()) {
                        val value = array.optJSONObject(index) ?: continue
                        val timestamp = value.optString("t").takeIf { it.isNotBlank() }
                            ?.let { runCatching { Instant.parse(it).epochSecond }.getOrNull() }
                            ?: continue
                        val open = value.optPositiveDouble("o") ?: continue
                        val high = value.optPositiveDouble("h") ?: continue
                        val low = value.optPositiveDouble("l") ?: continue
                        val close = value.optPositiveDouble("c") ?: continue
                        val volume = value.optLong("v", 0L).coerceAtLeast(0L)
                        if (high >= low) add(PriceBar(timestamp, open, high, low, close, volume))
                    }
                }
                if (bars.isNotEmpty()) put(symbol, bars)
            }
        }
        return BarsPage(
            bars = output,
            nextPageToken = root.optString("next_page_token").trim().takeIf { it.isNotBlank() && it != "null" }
        )
    }

    private fun executeJson(url: String, credentials: AlpacaCredentialsStore.Credentials): String {
        val request = authenticatedRequest(url, credentials)
        client.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            when (response.code) {
                401 -> throw AlpacaException("CREDENTIALS_INVALID", response.code, body)
                403 -> throw AlpacaException("PLAN_OR_FEED_RESTRICTED", response.code, body)
                429 -> throw AlpacaException("RATE_LIMITED", response.code, body)
            }
            if (!response.isSuccessful) throw AlpacaException("HTTP_ERROR", response.code, body)
            return body
        }
    }

    private fun authenticatedRequest(url: String, credentials: AlpacaCredentialsStore.Credentials): Request =
        Request.Builder().url(url)
            .header("APCA-API-KEY-ID", credentials.apiKey)
            .header("APCA-API-SECRET-KEY", credentials.secretKey)
            .header("Accept", "application/json")
            .header("User-Agent", "AnalistaAndroid/3.1")
            .build()

    private fun normalizeSymbols(symbols: List<String>): List<String> = symbols.asSequence()
        .map { it.trim().uppercase().replace('.', '-') }
        .filter { it.isNotBlank() }
        .distinct()
        .toList()

    private fun JSONObject.optPositiveDouble(key: String): Double? =
        if (has(key) && !isNull(key)) optDouble(key).takeIf { it.isFinite() && it > 0.0 } else null

    class AlpacaException(val status: String, val httpCode: Int, responseBody: String) :
        IOException("Alpaca $status ($httpCode)${responseBody.takeIf { it.isNotBlank() }?.let { ": ${it.take(160)}" } ?: ""}")

    companion object {
        private const val DATA_BASE = "https://data.alpaca.markets"
        private val ASSET_BASES = listOf("https://paper-api.alpaca.markets", "https://api.alpaca.markets")
        private const val MAX_BAR_PAGES = 20
    }
}
