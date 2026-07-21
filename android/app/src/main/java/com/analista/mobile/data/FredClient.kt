package com.analista.mobile.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.IOException
import java.time.LocalDate
import java.util.concurrent.TimeUnit

class FredClient(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .callTimeout(40, TimeUnit.SECONDS)
        .build()
) {
    data class Observation(val date: LocalDate, val value: Double)
    data class Series(val seriesId: String, val observations: List<Observation>, val capturedAtUtc: Long)

    suspend fun series(
        seriesId: String,
        apiKey: String,
        limit: Int = 120,
        nowUtc: Long = System.currentTimeMillis()
    ): Series = withContext(Dispatchers.IO) {
        require(seriesId.isNotBlank())
        require(apiKey.isNotBlank())
        require(limit in 1..10_000)
        val normalized = seriesId.trim().uppercase()
        val url = ENDPOINT.toHttpUrl().newBuilder()
            .addQueryParameter("series_id", normalized)
            .addQueryParameter("api_key", apiKey.trim())
            .addQueryParameter("file_type", "json")
            .addQueryParameter("sort_order", "desc")
            .addQueryParameter("limit", limit.toString())
            .build()
        val request = Request.Builder().url(url)
            .header("Accept", "application/json")
            .header("User-Agent", "AnalistaAndroid/3.1")
            .build()
        val result = runCatching {
            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (!response.isSuccessful) throw IOException("FRED HTTP ${response.code}")
                parseSeries(normalized, body, nowUtc)
            }
        }
        result.fold(
            onSuccess = { value ->
                SourceStatusRegistry.record(SourceStatus("MACRO_FRED", "FRED", "AVAILABLE", if (value.observations.isEmpty()) "EMPTY" else "COMPLETE", nowUtc))
                value
            },
            onFailure = { error ->
                SourceStatusRegistry.record(SourceStatus("MACRO_FRED", "FRED", "ERROR", "EMPTY", nowUtc, error.message))
                throw error
            }
        )
    }

    internal fun parseSeries(seriesId: String, json: String, capturedAtUtc: Long): Series {
        val root = JSONObject(json)
        val rows = root.optJSONArray("observations") ?: return Series(seriesId, emptyList(), capturedAtUtc)
        val observations = buildList {
            for (index in 0 until rows.length()) {
                val row = rows.optJSONObject(index) ?: continue
                val date = runCatching { LocalDate.parse(row.optString("date")) }.getOrNull() ?: continue
                val value = row.optString("value").toDoubleOrNull()?.takeIf { it.isFinite() } ?: continue
                add(Observation(date, value))
            }
        }.distinctBy { it.date }.sortedBy { it.date }
        return Series(seriesId.trim().uppercase(), observations, capturedAtUtc)
    }

    companion object {
        private const val ENDPOINT = "https://api.stlouisfed.org/fred/series/observations"
        val DEFAULT_SERIES = listOf(
            "DGS10", "DGS30", "DFF", "T10Y2Y", "WALCL", "RRPONTSYD", "M2SL", "CPIAUCSL", "UNRATE"
        )
    }
}
