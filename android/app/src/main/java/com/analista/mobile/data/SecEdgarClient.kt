package com.analista.mobile.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.IOException
import java.time.LocalDate
import java.util.concurrent.TimeUnit

class SecEdgarClient(
    private val userAgent: String,
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .callTimeout(40, TimeUnit.SECONDS)
        .build()
) {
    data class TickerCik(val ticker: String, val cik: String, val title: String?)
    data class FactPoint(
        val taxonomy: String,
        val concept: String,
        val unit: String,
        val value: Double,
        val filed: LocalDate?,
        val periodEnd: LocalDate?,
        val form: String?
    )
    data class InsiderFiling(
        val accessionNumber: String,
        val form: String,
        val filingDate: LocalDate?,
        val reportDate: LocalDate?,
        val primaryDocument: String?
    )

    init {
        require(userAgent.contains('@')) { "SEC user agent must contain a contact email" }
    }

    suspend fun tickerMap(nowUtc: Long = System.currentTimeMillis()): List<TickerCik> = withContext(Dispatchers.IO) {
        val result = runCatching { parseTickerMap(get(TICKERS_ENDPOINT)) }
        record("SEC_TICKER_MAP", result, nowUtc) { if (it.isEmpty()) "EMPTY" else "COMPLETE" }
        result.getOrThrow()
    }

    suspend fun companyFacts(cik: String, nowUtc: Long = System.currentTimeMillis()): List<FactPoint> = withContext(Dispatchers.IO) {
        val normalized = normalizeCik(cik)
        val result = runCatching { parseCompanyFacts(get("$DATA_BASE/api/xbrl/companyfacts/CIK$normalized.json")) }
        record("FUNDAMENTALS_SEC", result, nowUtc) { if (it.isEmpty()) "EMPTY" else "COMPLETE" }
        result.getOrThrow()
    }

    suspend fun recentInsiderFilings(cik: String, nowUtc: Long = System.currentTimeMillis()): List<InsiderFiling> =
        withContext(Dispatchers.IO) {
            val normalized = normalizeCik(cik)
            val result = runCatching { parseRecentInsiderFilings(get("$DATA_BASE/submissions/CIK$normalized.json")) }
            record("INSIDERS_SEC", result, nowUtc) { if (it.isEmpty()) "EMPTY" else "COMPLETE" }
            result.getOrThrow()
        }

    internal fun parseTickerMap(json: String): List<TickerCik> {
        val root = JSONObject(json)
        return buildList {
            val keys = root.keys()
            while (keys.hasNext()) {
                val row = root.optJSONObject(keys.next()) ?: continue
                val ticker = row.optString("ticker").trim().uppercase()
                val cik = row.optLong("cik_str", 0L).takeIf { it > 0L }?.toString()?.padStart(10, '0') ?: continue
                if (ticker.isNotBlank()) add(TickerCik(ticker, cik, row.optString("title").trim().takeIf { it.isNotBlank() }))
            }
        }.distinctBy { it.ticker }.sortedBy { it.ticker }
    }

    internal fun parseCompanyFacts(json: String): List<FactPoint> {
        val facts = JSONObject(json).optJSONObject("facts") ?: return emptyList()
        return buildList {
            val taxonomies = facts.keys()
            while (taxonomies.hasNext()) {
                val taxonomy = taxonomies.next()
                val concepts = facts.optJSONObject(taxonomy) ?: continue
                val conceptKeys = concepts.keys()
                while (conceptKeys.hasNext()) {
                    val concept = conceptKeys.next()
                    val units = concepts.optJSONObject(concept)?.optJSONObject("units") ?: continue
                    val unitKeys = units.keys()
                    while (unitKeys.hasNext()) {
                        val unit = unitKeys.next()
                        val values = units.optJSONArray(unit) ?: continue
                        for (index in 0 until values.length()) {
                            val row = values.optJSONObject(index) ?: continue
                            val value = row.optDouble("val").takeIf { it.isFinite() } ?: continue
                            add(
                                FactPoint(
                                    taxonomy = taxonomy,
                                    concept = concept,
                                    unit = unit,
                                    value = value,
                                    filed = row.optDate("filed"),
                                    periodEnd = row.optDate("end"),
                                    form = row.optString("form").trim().takeIf { it.isNotBlank() }
                                )
                            )
                        }
                    }
                }
            }
        }.sortedWith(compareBy<FactPoint> { it.concept }.thenByDescending { it.filed })
    }

    internal fun parseRecentInsiderFilings(json: String): List<InsiderFiling> {
        val recent = JSONObject(json).optJSONObject("filings")?.optJSONObject("recent") ?: return emptyList()
        val forms = recent.optJSONArray("form") ?: return emptyList()
        val accession = recent.optJSONArray("accessionNumber")
        val filingDates = recent.optJSONArray("filingDate")
        val reportDates = recent.optJSONArray("reportDate")
        val documents = recent.optJSONArray("primaryDocument")
        return buildList {
            for (index in 0 until forms.length()) {
                val form = forms.optString(index).trim().uppercase()
                if (form !in setOf("3", "4", "5", "3/A", "4/A", "5/A")) continue
                val accessionNumber = accession?.optString(index)?.trim().orEmpty()
                if (accessionNumber.isBlank()) continue
                add(
                    InsiderFiling(
                        accessionNumber = accessionNumber,
                        form = form,
                        filingDate = filingDates?.optString(index)?.toDate(),
                        reportDate = reportDates?.optString(index)?.toDate(),
                        primaryDocument = documents?.optString(index)?.trim()?.takeIf { it.isNotBlank() }
                    )
                )
            }
        }
    }

    private fun get(url: String): String {
        val request = Request.Builder().url(url)
            .header("User-Agent", userAgent)
            .header("Accept-Encoding", "gzip, deflate")
            .header("Host", url.substringAfter("https://").substringBefore('/'))
            .build()
        client.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) throw IOException("SEC HTTP ${response.code}")
            return body
        }
    }

    private fun <T> record(module: String, result: Result<List<T>>, nowUtc: Long, coverage: (List<T>) -> String) {
        result.fold(
            onSuccess = { SourceStatusRegistry.record(SourceStatus(module, "SEC_EDGAR", "AVAILABLE", coverage(it), nowUtc)) },
            onFailure = { SourceStatusRegistry.record(SourceStatus(module, "SEC_EDGAR", "ERROR", "EMPTY", nowUtc, it.message)) }
        )
    }

    private fun normalizeCik(value: String): String {
        val digits = value.filter(Char::isDigit)
        require(digits.isNotBlank() && digits.length <= 10)
        return digits.padStart(10, '0')
    }

    private fun JSONObject.optDate(key: String): LocalDate? = optString(key).toDate()
    private fun String.toDate(): LocalDate? = trim().takeIf { it.isNotBlank() }?.let { runCatching { LocalDate.parse(it) }.getOrNull() }

    companion object {
        private const val DATA_BASE = "https://data.sec.gov"
        private const val TICKERS_ENDPOINT = "https://www.sec.gov/files/company_tickers.json"
    }
}
