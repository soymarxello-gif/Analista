package com.analista.mobile.data

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit

class YahooFinanceClient(
    context: Context,
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .callTimeout(45, TimeUnit.SECONDS)
        .build()
) {
    private val cacheDir = File(context.cacheDir, "market-data").apply { mkdirs() }

    suspend fun dailyHistory(ticker: String, range: String = "1y"): FetchResult = withContext(Dispatchers.IO) {
        val safeTicker = ticker.trim().uppercase().replace(".", "-")
        val cache = File(cacheDir, "${safeTicker.replace("^", "IDX_").replace("=", "_")}_$range.json")
        var retries = 0
        var lastError: Throwable? = null
        val hosts = listOf("query1.finance.yahoo.com", "query2.finance.yahoo.com")
        repeat(3) { attempt ->
            hosts.forEach { host ->
                try {
                    val url = "https://$host/v8/finance/chart/$safeTicker?range=$range&interval=1d&events=div%2Csplits"
                    val request = Request.Builder().url(url)
                        .header("User-Agent", "Mozilla/5.0 AnalistaAndroid/2.0")
                        .header("Accept", "application/json").build()
                    client.newCall(request).execute().use { response ->
                        if (!response.isSuccessful) throw IOException("Yahoo HTTP ${response.code} for $safeTicker")
                        val body = response.body?.string() ?: throw IOException("Yahoo empty body for $safeTicker")
                        val bars = parseChart(body, safeTicker)
                        cache.writeText(body)
                        val source = "Yahoo/$host"
                        HistorySourceRegistry.record(safeTicker, source)
                        MarketHistoryRegistry.record(safeTicker, bars)
                        return@withContext FetchResult(bars, source, false, retries)
                    }
                } catch (error: Throwable) {
                    lastError = error
                }
            }
            if (attempt < 2) {
                retries += 1
                delay(500L shl attempt)
            }
        }
        if (cache.exists() && System.currentTimeMillis() - cache.lastModified() <= CACHE_MAX_AGE_MS) {
            val source = "Yahoo/cache"
            HistorySourceRegistry.record(safeTicker, source)
            val bars = parseChart(cache.readText(), safeTicker)
            MarketHistoryRegistry.record(safeTicker, bars)
            return@withContext FetchResult(bars, source, true, retries)
        }
        throw IOException(lastError?.message ?: "No data for $safeTicker", lastError)
    }

    suspend fun marketQuote(ticker: String): MarketQuote = withContext(Dispatchers.IO) {
        val safeTicker = ticker.trim().uppercase().replace(".", "-")
        val body = getJson("https://query1.finance.yahoo.com/v7/finance/quote?symbols=$safeTicker")
        parseMarketQuote(body, safeTicker)
    }

    internal fun parseMarketQuote(
        json: String,
        ticker: String,
        retrievedAtUtc: Long = System.currentTimeMillis()
    ): MarketQuote {
        val result = JSONObject(json)
            .optJSONObject("quoteResponse")
            ?.optJSONArray("result")
            ?.optJSONObject(0)
            ?: throw IOException("No quote for $ticker")
        val marketState = result.optString("marketState").takeIf { it.isNotBlank() }
        val providerTimestamp = providerTimestampMillis(result, marketState)
        return MarketQuote(
            bid = result.optNullableDouble("bid"),
            ask = result.optNullableDouble("ask"),
            regularMarketPrice = result.optNullableDouble("regularMarketPrice"),
            preMarketPrice = result.optNullableDouble("preMarketPrice"),
            marketCap = result.optNullableLong("marketCap"),
            quoteType = result.optString("quoteType").takeIf { it.isNotBlank() },
            marketState = marketState,
            capturedAtUtc = providerTimestamp ?: retrievedAtUtc,
            providerTimestampUtc = providerTimestamp,
            retrievedAtUtc = retrievedAtUtc,
            provider = "YAHOO"
        )
    }

    private fun providerTimestampMillis(result: JSONObject, marketState: String?): Long? {
        val keys = when (marketState?.uppercase()) {
            "PRE", "PREPRE" -> listOf("preMarketTime", "regularMarketTime", "postMarketTime")
            "POST", "POSTPOST" -> listOf("postMarketTime", "regularMarketTime", "preMarketTime")
            else -> listOf("regularMarketTime", "preMarketTime", "postMarketTime")
        }
        return keys.asSequence()
            .mapNotNull { key -> result.optLong(key, 0L).takeIf { it > 0L } }
            .firstOrNull()
            ?.times(1_000L)
    }

    internal fun parseChart(json: String, ticker: String): List<PriceBar> {
        val root = JSONObject(json)
        val chart = root.getJSONObject("chart")
        if (!chart.isNull("error")) throw IOException("Yahoo error for $ticker: ${chart.get("error")}")
        val resultArray = chart.optJSONArray("result") ?: throw IOException("Yahoo missing result for $ticker")
        if (resultArray.length() == 0) throw IOException("Yahoo empty result for $ticker")
        val result = resultArray.getJSONObject(0)
        val timestamps = result.getJSONArray("timestamp")
        val quote = result.getJSONObject("indicators").getJSONArray("quote").getJSONObject(0)
        val opens = quote.getJSONArray("open")
        val highs = quote.getJSONArray("high")
        val lows = quote.getJSONArray("low")
        val closes = quote.getJSONArray("close")
        val volumes = quote.getJSONArray("volume")
        val bars = ArrayList<PriceBar>(timestamps.length())
        for (i in 0 until timestamps.length()) {
            if (opens.isNull(i) || highs.isNull(i) || lows.isNull(i) || closes.isNull(i)) continue
            val bar = PriceBar(
                epochSeconds = timestamps.getLong(i), open = opens.getDouble(i), high = highs.getDouble(i),
                low = lows.getDouble(i), close = closes.getDouble(i),
                volume = if (volumes.isNull(i)) 0L else volumes.getLong(i)
            )
            if (bar.close.isFinite() && bar.close > 0) bars += bar
        }
        if (bars.size < 60) throw IOException("Insufficient history for $ticker: ${bars.size}")
        return bars
    }

    suspend fun fundamentals(ticker: String): FundamentalMetrics = withContext(Dispatchers.IO) {
        val safeTicker = ticker.trim().uppercase().replace(".", "-")
        val modules = "defaultKeyStatistics,financialData,summaryDetail"
        val body = getJson("https://query1.finance.yahoo.com/v10/finance/quoteSummary/$safeTicker?modules=$modules")
        parseFundamentals(body, safeTicker)
    }

    suspend fun options(ticker: String): OptionsMetrics = withContext(Dispatchers.IO) {
        val safeTicker = ticker.trim().uppercase().replace(".", "-")
        val body = getJson("https://query2.finance.yahoo.com/v7/finance/options/$safeTicker")
        parseOptions(body, safeTicker)
    }

    private fun getJson(url: String): String {
        val request = Request.Builder().url(url)
            .header("User-Agent", "Mozilla/5.0 AnalistaAndroid/2.0")
            .header("Accept", "application/json").build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) throw IOException("Yahoo HTTP ${response.code}")
            return response.body?.string() ?: throw IOException("Yahoo empty body")
        }
    }

    internal fun parseFundamentals(json: String, ticker: String): FundamentalMetrics {
        val root = JSONObject(json)
        val response = root.optJSONObject("quoteSummary") ?: throw IOException("Missing quoteSummary for $ticker")
        if (!response.isNull("error")) throw IOException("Yahoo fundamentals error for $ticker")
        val result = response.optJSONArray("result")?.optJSONObject(0)
            ?: throw IOException("No fundamentals for $ticker")
        val stats = result.optJSONObject("defaultKeyStatistics") ?: JSONObject()
        val financial = result.optJSONObject("financialData") ?: JSONObject()
        val summary = result.optJSONObject("summaryDetail") ?: JSONObject()
        return FundamentalMetrics(
            marketCap = rawLong(summary, "marketCap"),
            trailingPe = rawDouble(summary, "trailingPE"),
            priceToSales = rawDouble(summary, "priceToSalesTrailing12Months"),
            epsTrailing = rawDouble(stats, "trailingEps"),
            revenueGrowthPct = rawDouble(financial, "revenueGrowth")?.times(100.0),
            grossMarginPct = rawDouble(financial, "grossMargins")?.times(100.0),
            operatingMarginPct = rawDouble(financial, "operatingMargins")?.times(100.0),
            profitMarginPct = rawDouble(financial, "profitMargins")?.times(100.0),
            debtToEquity = rawDouble(financial, "debtToEquity")
        )
    }

    internal fun parseOptions(json: String, ticker: String): OptionsMetrics {
        val root = JSONObject(json)
        val result = root.optJSONObject("optionChain")?.optJSONArray("result")?.optJSONObject(0)
            ?: throw IOException("No options for $ticker")
        val options = result.optJSONArray("options")?.optJSONObject(0)
            ?: return OptionsMetrics(null, null, null, null)
        val calls = options.optJSONArray("calls")
        val puts = options.optJSONArray("puts")
        fun sumOi(array: org.json.JSONArray?): Long {
            if (array == null) return 0L
            var total = 0L
            for (i in 0 until array.length()) total += array.optJSONObject(i)?.optLong("openInterest", 0L) ?: 0L
            return total
        }
        val callOi = sumOi(calls)
        val putOi = sumOi(puts)
        return OptionsMetrics(
            putCallOi = if (callOi > 0) putOi.toDouble() / callOi else null,
            nearCallOi = callOi.takeIf { it > 0 },
            nearPutOi = putOi.takeIf { it > 0 },
            expiry = options.optLong("expirationDate", 0L).takeIf { it > 0 }
        )
    }

    private fun rawDouble(parent: JSONObject, key: String): Double? {
        val value = parent.optJSONObject(key) ?: return null
        return if (value.has("raw") && !value.isNull("raw")) value.optDouble("raw").takeIf { it.isFinite() } else null
    }

    private fun rawLong(parent: JSONObject, key: String): Long? {
        val value = parent.optJSONObject(key) ?: return null
        return if (value.has("raw") && !value.isNull("raw")) value.optLong("raw").takeIf { it > 0L } else null
    }

    private fun JSONObject.optNullableDouble(key: String): Double? =
        if (has(key) && !isNull(key)) optDouble(key).takeIf { it.isFinite() && it > 0.0 } else null

    private fun JSONObject.optNullableLong(key: String): Long? =
        if (has(key) && !isNull(key)) optLong(key).takeIf { it > 0L } else null

    companion object { private const val CACHE_MAX_AGE_MS = 72L * 60 * 60 * 1000 }
}
