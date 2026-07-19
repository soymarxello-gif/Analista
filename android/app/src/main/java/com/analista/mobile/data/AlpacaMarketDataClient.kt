package com.analista.mobile.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.IOException
import java.time.Instant
import java.util.concurrent.TimeUnit

class AlpacaMarketDataClient(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(25, TimeUnit.SECONDS)
        .callTimeout(35, TimeUnit.SECONDS)
        .build()
) {
    data class AlpacaQuote(
        val symbol: String,
        val bid: Double?,
        val ask: Double?,
        val timestampUtcMillis: Long?,
        val feed: String
    )

    data class ConnectionResult(val ok: Boolean, val status: String, val message: String)

    suspend fun latestQuotes(
        symbols: List<String>,
        credentials: AlpacaCredentialsStore.Credentials
    ): Map<String, AlpacaQuote> = withContext(Dispatchers.IO) {
        if (symbols.isEmpty()) return@withContext emptyMap()
        val normalized = symbols.map { it.trim().uppercase() }.distinct()
        val url = "https://data.alpaca.markets/v2/stocks/quotes/latest".toHttpUrl().newBuilder()
            .addQueryParameter("symbols", normalized.joinToString(","))
            .addQueryParameter("feed", credentials.feed)
            .build()
        val request = authenticatedRequest(url.toString(), credentials)
        client.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            when (response.code) {
                401 -> throw AlpacaException("CREDENTIALS_INVALID", response.code, body)
                403 -> throw AlpacaException("PLAN_OR_FEED_RESTRICTED", response.code, body)
                429 -> throw AlpacaException("RATE_LIMITED", response.code, body)
            }
            if (!response.isSuccessful) throw AlpacaException("HTTP_ERROR", response.code, body)
            parseLatestQuotes(body, credentials.feed)
        }
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

    private fun authenticatedRequest(url: String, credentials: AlpacaCredentialsStore.Credentials): Request =
        Request.Builder().url(url)
            .header("APCA-API-KEY-ID", credentials.apiKey)
            .header("APCA-API-SECRET-KEY", credentials.secretKey)
            .header("Accept", "application/json")
            .header("User-Agent", "AnalistaAndroid/2.0")
            .build()

    private fun JSONObject.optPositiveDouble(key: String): Double? =
        if (has(key) && !isNull(key)) optDouble(key).takeIf { it.isFinite() && it > 0.0 } else null

    class AlpacaException(val status: String, val httpCode: Int, responseBody: String) :
        IOException("Alpaca $status ($httpCode)${responseBody.takeIf { it.isNotBlank() }?.let { ": ${it.take(160)}" } ?: ""}")
}
