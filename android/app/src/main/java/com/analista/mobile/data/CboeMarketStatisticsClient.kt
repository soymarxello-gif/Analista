package com.analista.mobile.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException
import java.util.concurrent.TimeUnit

class CboeMarketStatisticsClient(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .callTimeout(40, TimeUnit.SECONDS)
        .build()
) {
    data class Ratios(
        val totalPutCall: Double?,
        val indexPutCall: Double?,
        val equityPutCall: Double?,
        val vixPutCall: Double?,
        val spxPutCall: Double?,
        val capturedAtUtc: Long
    ) {
        val coverageCount: Int get() = listOf(totalPutCall, indexPutCall, equityPutCall, vixPutCall, spxPutCall).count { it != null }
    }

    suspend fun currentRatios(nowUtc: Long = System.currentTimeMillis()): Ratios = withContext(Dispatchers.IO) {
        val request = Request.Builder().url(ENDPOINT)
            .header("Accept", "text/html,application/xhtml+xml")
            .header("User-Agent", "Mozilla/5.0 AnalistaAndroid/3.1")
            .build()
        val result = runCatching {
            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (!response.isSuccessful) throw IOException("Cboe HTTP ${response.code}")
                parseRatios(body, nowUtc)
            }
        }
        result.fold(
            onSuccess = { ratios ->
                SourceStatusRegistry.record(
                    SourceStatus(
                        module = "OPTIONS_MARKET_CONTEXT",
                        provider = "CBOE",
                        status = if (ratios.coverageCount > 0) "AVAILABLE" else "DEGRADED",
                        coverage = when (ratios.coverageCount) {
                            5 -> "COMPLETE"
                            0 -> "EMPTY"
                            else -> "PARTIAL"
                        },
                        capturedAtUtc = nowUtc
                    )
                )
                ratios
            },
            onFailure = { error ->
                SourceStatusRegistry.record(SourceStatus("OPTIONS_MARKET_CONTEXT", "CBOE", "ERROR", "EMPTY", nowUtc, error.message))
                throw error
            }
        )
    }

    internal fun parseRatios(html: String, capturedAtUtc: Long): Ratios {
        val text = html
            .replace(Regex("<script[\\s\\S]*?</script>", RegexOption.IGNORE_CASE), " ")
            .replace(Regex("<style[\\s\\S]*?</style>", RegexOption.IGNORE_CASE), " ")
            .replace(Regex("<[^>]+>"), " ")
            .replace("&nbsp;", " ")
            .replace(Regex("\\s+"), " ")
        return Ratios(
            totalPutCall = findRatio(text, "TOTAL PUT/CALL RATIO"),
            indexPutCall = findRatio(text, "INDEX PUT/CALL RATIO"),
            equityPutCall = findRatio(text, "EQUITY PUT/CALL RATIO"),
            vixPutCall = findRatio(text, "CBOE VOLATILITY INDEX (VIX) PUT/CALL RATIO"),
            spxPutCall = findRatio(text, "SPX + SPXW PUT/CALL RATIO"),
            capturedAtUtc = capturedAtUtc
        )
    }

    private fun findRatio(text: String, label: String): Double? {
        val pattern = Regex("${Regex.escape(label)}\\s+([0-9]+(?:\\.[0-9]+)?)", RegexOption.IGNORE_CASE)
        return pattern.find(text)?.groupValues?.getOrNull(1)?.toDoubleOrNull()
    }

    companion object {
        private const val ENDPOINT = "https://www.cboe.com/data/mktstat.aspx"
    }
}
