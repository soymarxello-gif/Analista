package com.analista.mobile.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class NasdaqScreenerClient(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(35, TimeUnit.SECONDS)
        .callTimeout(45, TimeUnit.SECONDS)
        .build()
) {
    data class StockMetadata(
        val symbol: String,
        val name: String?,
        val marketCap: Long?,
        val country: String?,
        val sector: String?,
        val industry: String?
    )

    suspend fun stocks(limit: Int = 5_000): List<StockMetadata> = withContext(Dispatchers.IO) {
        require(limit in 1..10_000)
        val url = ENDPOINT.toHttpUrl().newBuilder()
            .addQueryParameter("tableonly", "true")
            .addQueryParameter("limit", limit.toString())
            .addQueryParameter("offset", "0")
            .addQueryParameter("download", "true")
            .build()
        val request = Request.Builder().url(url)
            .header("Accept", "application/json, text/plain, */*")
            .header("Accept-Language", "en-US,en;q=0.9")
            .header("Origin", "https://www.nasdaq.com")
            .header("Referer", "https://www.nasdaq.com/market-activity/stocks/screener")
            .header("User-Agent", "Mozilla/5.0 (Linux; Android 15) AnalistaAndroid/3.1")
            .build()
        client.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) throw IOException("Nasdaq screener HTTP ${response.code}")
            parseStocks(body)
        }
    }

    internal fun parseStocks(json: String): List<StockMetadata> {
        val rows = JSONObject(json)
            .optJSONObject("data")
            ?.optJSONObject("table")
            ?.optJSONArray("rows")
            ?: return emptyList()
        return buildList {
            for (index in 0 until rows.length()) {
                val row = rows.optJSONObject(index) ?: continue
                val symbol = row.optString("symbol").trim().uppercase().replace('.', '-')
                if (symbol.isBlank()) continue
                add(
                    StockMetadata(
                        symbol = symbol,
                        name = clean(row.optString("name")),
                        marketCap = parseMarketCap(row.opt("marketCap")),
                        country = clean(row.optString("country")),
                        sector = clean(row.optString("sector")),
                        industry = clean(row.optString("industry"))
                    )
                )
            }
        }.distinctBy { it.symbol }
    }

    internal fun parseMarketCap(raw: Any?): Long? {
        if (raw == null || raw == JSONObject.NULL) return null
        if (raw is Number) return raw.toDouble().takeIf { it.isFinite() && it > 0.0 }?.toLong()
        val text = raw.toString().trim()
        if (text.isBlank() || text.equals("n/a", true) || text == "--") return null
        val normalized = text.replace("$", "").replace(",", "").trim().uppercase()
        val multiplier = when {
            normalized.endsWith("T") -> 1_000_000_000_000.0
            normalized.endsWith("B") -> 1_000_000_000.0
            normalized.endsWith("M") -> 1_000_000.0
            else -> 1.0
        }
        val numeric = if (multiplier == 1.0) normalized else normalized.dropLast(1)
        return numeric.toDoubleOrNull()?.takeIf { it.isFinite() && it > 0.0 }?.times(multiplier)?.toLong()
    }

    private fun clean(value: String): String? = value.trim().takeIf { it.isNotBlank() && !it.equals("n/a", true) }

    companion object {
        private const val ENDPOINT = "https://api.nasdaq.com/api/screener/stocks"
    }
}
