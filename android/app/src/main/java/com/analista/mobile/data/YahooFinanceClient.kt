package com.analista.mobile.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class YahooFinanceClient(
    private val client: OkHttpClient = OkHttpClient.Builder().connectTimeout(15, TimeUnit.SECONDS).readTimeout(30, TimeUnit.SECONDS).callTimeout(45, TimeUnit.SECONDS).build()
) {
    suspend fun dailyHistory(ticker: String, range: String = "1y"): List<PriceBar> = withContext(Dispatchers.IO) {
        val safeTicker = ticker.trim().uppercase().replace(".", "-")
        val url = "https://query1.finance.yahoo.com/v8/finance/chart/$safeTicker?range=$range&interval=1d&events=div%2Csplits"
        val request = Request.Builder().url(url).header("User-Agent", "Mozilla/5.0 AnalistaAndroid/1.0").header("Accept", "application/json").build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) throw IOException("Yahoo HTTP ${response.code} for $safeTicker")
            parseChart(response.body?.string() ?: throw IOException("Yahoo empty body for $safeTicker"), safeTicker)
        }
    }

    internal fun parseChart(json: String, ticker: String): List<PriceBar> {
        val chart = JSONObject(json).getJSONObject("chart")
        if (!chart.isNull("error")) throw IOException("Yahoo error for $ticker: ${chart.get("error")}")
        val result = chart.getJSONArray("result").getJSONObject(0)
        val timestamps = result.getJSONArray("timestamp")
        val quote = result.getJSONObject("indicators").getJSONArray("quote").getJSONObject(0)
        val opens = quote.getJSONArray("open"); val highs = quote.getJSONArray("high")
        val lows = quote.getJSONArray("low"); val closes = quote.getJSONArray("close"); val volumes = quote.getJSONArray("volume")
        val bars = ArrayList<PriceBar>(timestamps.length())
        for (i in 0 until timestamps.length()) {
            if (opens.isNull(i) || highs.isNull(i) || lows.isNull(i) || closes.isNull(i)) continue
            val bar = PriceBar(timestamps.getLong(i), opens.getDouble(i), highs.getDouble(i), lows.getDouble(i), closes.getDouble(i), if (volumes.isNull(i)) 0L else volumes.getLong(i))
            if (bar.close.isFinite() && bar.close > 0) bars += bar
        }
        if (bars.size < 60) throw IOException("Insufficient history for $ticker: ${bars.size}")
        return bars
    }
}
