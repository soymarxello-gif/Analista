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
                        .header("User-Agent", "Mozilla/5.0 AnalistaAndroid/1.1")
                        .header("Accept", "application/json").build()
                    client.newCall(request).execute().use { response ->
                        if (!response.isSuccessful) throw IOException("Yahoo HTTP ${response.code} for $safeTicker")
                        val body = response.body?.string() ?: throw IOException("Yahoo empty body for $safeTicker")
                        val bars = parseChart(body, safeTicker)
                        cache.writeText(body)
                        return@withContext FetchResult(bars, "Yahoo/$host", false, retries)
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
            return@withContext FetchResult(parseChart(cache.readText(), safeTicker), "Yahoo/cache", true, retries)
        }
        throw IOException(lastError?.message ?: "No data for $safeTicker", lastError)
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

    companion object { private const val CACHE_MAX_AGE_MS = 72L * 60 * 60 * 1000 }
}
