package com.analista.mobile.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.time.LocalDate
import java.util.concurrent.TimeUnit

class CftcCotClient(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(35, TimeUnit.SECONDS)
        .callTimeout(45, TimeUnit.SECONDS)
        .build()
) {
    data class Positioning(
        val market: String,
        val reportDate: LocalDate,
        val assetManagerLong: Long?,
        val assetManagerShort: Long?,
        val leveragedFundsLong: Long?,
        val leveragedFundsShort: Long?,
        val dealerLong: Long?,
        val dealerShort: Long?
    ) {
        val assetManagerNet: Long? get() = net(assetManagerLong, assetManagerShort)
        val leveragedFundsNet: Long? get() = net(leveragedFundsLong, leveragedFundsShort)
        private fun net(long: Long?, short: Long?): Long? = if (long != null && short != null) long - short else null
    }

    suspend fun latest(
        marketContains: String? = null,
        limit: Int = 1_000,
        nowUtc: Long = System.currentTimeMillis()
    ): List<Positioning> = withContext(Dispatchers.IO) {
        require(limit in 1..5_000)
        val builder = ENDPOINT.toHttpUrl().newBuilder()
            .addQueryParameter("$limit", limit.toString())
            .addQueryParameter("$order", "report_date_as_yyyy_mm_dd DESC")
        marketContains?.trim()?.takeIf { it.isNotBlank() }?.let { value ->
            val escaped = value.uppercase().replace("'", "''")
            builder.addQueryParameter("$where", "upper(market_and_exchange_names) like '%$escaped%'")
        }
        val request = Request.Builder().url(builder.build())
            .header("Accept", "application/json")
            .header("User-Agent", "AnalistaAndroid/3.1")
            .build()
        val result = runCatching {
            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (!response.isSuccessful) throw IOException("CFTC HTTP ${response.code}")
                parse(body)
            }
        }
        result.fold(
            onSuccess = { rows ->
                SourceStatusRegistry.record(SourceStatus("FUTURES_POSITIONING", "CFTC_COT", "AVAILABLE", if (rows.isEmpty()) "EMPTY" else "COMPLETE", nowUtc))
                rows
            },
            onFailure = { error ->
                SourceStatusRegistry.record(SourceStatus("FUTURES_POSITIONING", "CFTC_COT", "ERROR", "EMPTY", nowUtc, error.message))
                throw error
            }
        )
    }

    internal fun parse(json: String): List<Positioning> {
        val rows = JSONArray(json)
        return buildList {
            for (index in 0 until rows.length()) {
                val row = rows.optJSONObject(index) ?: continue
                val market = row.firstString("market_and_exchange_names", "market_and_exchange_name") ?: continue
                val date = row.firstString("report_date_as_yyyy_mm_dd", "report_date")
                    ?.substringBefore('T')
                    ?.let { runCatching { LocalDate.parse(it) }.getOrNull() }
                    ?: continue
                add(
                    Positioning(
                        market = market,
                        reportDate = date,
                        assetManagerLong = row.firstLong("asset_mgr_positions_long", "asset_mgr_positions_long_all"),
                        assetManagerShort = row.firstLong("asset_mgr_positions_short", "asset_mgr_positions_short_all"),
                        leveragedFundsLong = row.firstLong("lev_money_positions_long", "lev_money_positions_long_all"),
                        leveragedFundsShort = row.firstLong("lev_money_positions_short", "lev_money_positions_short_all"),
                        dealerLong = row.firstLong("dealer_positions_long", "dealer_positions_long_all"),
                        dealerShort = row.firstLong("dealer_positions_short", "dealer_positions_short_all")
                    )
                )
            }
        }.distinctBy { it.market to it.reportDate }.sortedByDescending { it.reportDate }
    }

    private fun JSONObject.firstString(vararg keys: String): String? = keys.asSequence()
        .map { optString(it).trim() }
        .firstOrNull { it.isNotBlank() }

    private fun JSONObject.firstLong(vararg keys: String): Long? = keys.asSequence()
        .mapNotNull { key ->
            if (!has(key) || isNull(key)) null
            else optString(key).replace(",", "").toDoubleOrNull()?.toLong()
        }
        .firstOrNull()

    companion object {
        private const val ENDPOINT = "https://publicreporting.cftc.gov/resource/udgc-27he.json"
    }
}
