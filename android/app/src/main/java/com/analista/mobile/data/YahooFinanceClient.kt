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
import java.time.Instant
import java.time.temporal.ChronoUnit
import java.util.concurrent.TimeUnit
import kotlin.math.abs

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
        val safeTicker = yahooTicker(ticker)
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
        val safeTicker = yahooTicker(ticker)
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
        val safeTicker = yahooTicker(ticker)
        val modules = listOf(
            "defaultKeyStatistics", "financialData", "summaryDetail", "assetProfile",
            "incomeStatementHistoryQuarterly", "cashflowStatementHistoryQuarterly",
            "balanceSheetHistoryQuarterly", "calendarEvents"
        ).joinToString(",")
        val body = getJson("https://query1.finance.yahoo.com/v10/finance/quoteSummary/$safeTicker?modules=$modules")
        val metrics = parseFundamentals(body, safeTicker)
        FundamentalSnapshotRegistry.record(safeTicker, metrics)
        metrics
    }

    suspend fun options(ticker: String): OptionsMetrics = withContext(Dispatchers.IO) {
        val safeTicker = yahooTicker(ticker)
        val baseUrl = "https://query2.finance.yahoo.com/v7/finance/options/$safeTicker"
        val first = parseOptionChain(getJson(baseUrl), safeTicker)
        val loadedExpiries = first.expiries.map { it.expiryEpochSeconds }.toSet()
        val remaining = (MAX_OPTION_EXPIRIES - first.expiries.size).coerceAtLeast(0)
        val additional = first.availableExpiries
            .filterNot { it in loadedExpiries }
            .take(remaining)
            .mapNotNull { expiry ->
                runCatching { parseOptionChain(getJson("$baseUrl?date=$expiry"), safeTicker) }.getOrNull()
            }
        val combined = mergeOptionChains(listOf(first) + additional)
        OptionChainRegistry.record(combined)
        combined.toLegacyMetrics()
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

    internal fun parseFundamentals(
        json: String,
        ticker: String,
        nowUtcMillis: Long = System.currentTimeMillis()
    ): FundamentalMetrics {
        val root = JSONObject(json)
        val response = root.optJSONObject("quoteSummary") ?: throw IOException("Missing quoteSummary for $ticker")
        if (!response.isNull("error")) throw IOException("Yahoo fundamentals error for $ticker")
        val result = response.optJSONArray("result")?.optJSONObject(0)
            ?: throw IOException("No fundamentals for $ticker")
        val stats = result.optJSONObject("defaultKeyStatistics") ?: JSONObject()
        val financial = result.optJSONObject("financialData") ?: JSONObject()
        val summary = result.optJSONObject("summaryDetail") ?: JSONObject()
        val profile = result.optJSONObject("assetProfile") ?: JSONObject()
        val income = statements(result, "incomeStatementHistoryQuarterly", "incomeStatementHistory")
        val cashFlow = statements(result, "cashflowStatementHistoryQuarterly", "cashflowStatements")
        val balance = statements(result, "balanceSheetHistoryQuarterly", "balanceSheetStatements")
        val latestIncome = income.getOrNull(0)
        val priorIncome = income.getOrNull(1)
        val yearAgoIncome = income.getOrNull(4)

        val latestRevenue = latestIncome?.let { rawNumber(it, "totalRevenue") }
        val priorRevenue = priorIncome?.let { rawNumber(it, "totalRevenue") }
        val yearAgoRevenue = yearAgoIncome?.let { rawNumber(it, "totalRevenue") }
        val latestEps = latestIncome?.let { rawNumber(it, "dilutedEPS") ?: rawNumber(it, "basicEPS") }
        val priorEps = priorIncome?.let { rawNumber(it, "dilutedEPS") ?: rawNumber(it, "basicEPS") }
        val yearAgoEps = yearAgoIncome?.let { rawNumber(it, "dilutedEPS") ?: rawNumber(it, "basicEPS") }

        val revenueYoy = pctChange(latestRevenue, yearAgoRevenue)
            ?: rawDouble(financial, "revenueGrowth")?.times(100.0)
        val epsYoy = pctChange(latestEps, yearAgoEps)
        val latestGrossMargin = margin(latestIncome, "grossProfit", latestRevenue)
            ?: rawDouble(financial, "grossMargins")?.times(100.0)
        val priorGrossMargin = margin(priorIncome, "grossProfit", priorRevenue)
        val latestOperatingMargin = margin(latestIncome, "operatingIncome", latestRevenue)
            ?: rawDouble(financial, "operatingMargins")?.times(100.0)
        val priorOperatingMargin = margin(priorIncome, "operatingIncome", priorRevenue)
        val latestNetMargin = margin(latestIncome, "netIncome", latestRevenue)
            ?: rawDouble(financial, "profitMargins")?.times(100.0)
        val priorNetMargin = margin(priorIncome, "netIncome", priorRevenue)

        val totalDebt = rawDouble(financial, "totalDebt")
            ?: balance.firstOrNull()?.let { rawNumber(it, "totalDebt") }
        val ebitda = rawDouble(financial, "ebitda")
        val latestEbit = latestIncome?.let { rawNumber(it, "ebit") ?: rawNumber(it, "operatingIncome") }
        val interestExpense = latestIncome?.let { rawNumber(it, "interestExpense") }?.let(::abs)
        val latestCashFlow = cashFlow.firstOrNull()
        val freeCashFlow = rawDouble(financial, "freeCashflow") ?: run {
            val operating = latestCashFlow?.let { rawNumber(it, "totalCashFromOperatingActivities") }
            val capex = latestCashFlow?.let { rawNumber(it, "capitalExpenditures") }
            if (operating != null && capex != null) operating + capex else null
        }
        val latestStatementEpoch = listOfNotNull(
            latestIncome?.let { rawLong(it, "endDate") },
            latestCashFlow?.let { rawLong(it, "endDate") },
            balance.firstOrNull()?.let { rawLong(it, "endDate") }
        ).maxOrNull()
        val earningsDateUtc = result.optJSONObject("calendarEvents")
            ?.optJSONObject("earnings")
            ?.optJSONArray("earningsDate")
            ?.optJSONObject(0)
            ?.let { rawLong(it, "raw") ?: it.optLong("raw", 0L).takeIf { value -> value > 0L } }
            ?.times(1_000L)
        val dataAgeDays = latestStatementEpoch?.let { epoch ->
            ChronoUnit.DAYS.between(Instant.ofEpochSecond(epoch), Instant.ofEpochMilli(nowUtcMillis)).coerceAtLeast(0L)
        }

        return FundamentalMetrics(
            marketCap = rawLong(summary, "marketCap"),
            trailingPe = rawDouble(summary, "trailingPE"),
            priceToSales = rawDouble(summary, "priceToSalesTrailing12Months"),
            epsTrailing = rawDouble(stats, "trailingEps"),
            revenueGrowthPct = rawDouble(financial, "revenueGrowth")?.times(100.0),
            grossMarginPct = latestGrossMargin,
            operatingMarginPct = latestOperatingMargin,
            profitMarginPct = latestNetMargin,
            debtToEquity = rawDouble(financial, "debtToEquity"),
            revenueYoyPct = revenueYoy,
            revenueTrend = trend(latestRevenue, priorRevenue, revenueYoy),
            epsYoyPct = epsYoy,
            epsTrend = trend(latestEps, priorEps, epsYoy),
            grossMarginDeltaPct = delta(latestGrossMargin, priorGrossMargin),
            operatingMarginDeltaPct = delta(latestOperatingMargin, priorOperatingMargin),
            netMarginDeltaPct = delta(latestNetMargin, priorNetMargin),
            debtToEbitda = if (totalDebt != null && ebitda != null && ebitda > 0.0) totalDebt / ebitda else null,
            interestCoverage = if (latestEbit != null && interestExpense != null && interestExpense > 0.0) latestEbit / interestExpense else null,
            freeCashFlow = freeCashFlow,
            sectorPriceToSalesMedian = null,
            earningsDateUtc = earningsDateUtc,
            earningsSessions = null,
            dataAgeDays = dataAgeDays,
            sector = profile.optString("sector").takeIf { it.isNotBlank() }
        )
    }

    internal fun parseOptionChain(
        json: String,
        ticker: String,
        capturedAtUtc: Long = System.currentTimeMillis()
    ): OptionChainSnapshot = YahooOptionChainParser.parse(json, ticker, capturedAtUtc)

    internal fun mergeOptionChains(chains: List<OptionChainSnapshot>): OptionChainSnapshot {
        require(chains.isNotEmpty()) { "option chains required" }
        val tickers = chains.map { it.ticker }.toSet()
        require(tickers.size == 1) { "option chains must belong to one ticker" }
        val first = chains.first()
        val expiries = chains.flatMap { it.expiries }
            .distinctBy { it.expiryEpochSeconds }
            .sortedBy { it.expiryEpochSeconds }
        return OptionChainSnapshot(
            ticker = first.ticker,
            spot = chains.firstNotNullOfOrNull { it.spot },
            expiries = expiries,
            availableExpiries = chains.flatMap { it.availableExpiries }.distinct().sorted(),
            capturedAtUtc = chains.maxOf { it.capturedAtUtc },
            provider = first.provider,
            providerHost = first.providerHost,
            gammaStatus = if (chains.any { it.gammaStatus == "AVAILABLE" }) "AVAILABLE" else "UNKNOWN"
        )
    }

    internal fun parseOptions(json: String, ticker: String): OptionsMetrics {
        val chain = parseOptionChain(json, ticker)
        OptionChainRegistry.record(chain)
        return chain.toLegacyMetrics()
    }

    private fun statements(result: JSONObject, module: String, key: String): List<JSONObject> {
        val array = result.optJSONObject(module)?.optJSONArray(key) ?: return emptyList()
        return (0 until array.length()).mapNotNull { array.optJSONObject(it) }
            .sortedByDescending { rawLong(it, "endDate") ?: 0L }
    }

    private fun margin(statement: JSONObject?, numeratorKey: String, revenue: Double?): Double? {
        val numerator = statement?.let { rawNumber(it, numeratorKey) }
        return if (numerator != null && revenue != null && revenue != 0.0) numerator / revenue * 100.0 else null
    }

    private fun pctChange(latest: Double?, prior: Double?): Double? =
        if (latest != null && prior != null && abs(prior) > 0.000001) (latest / abs(prior) - 1.0) * 100.0 else null

    private fun delta(latest: Double?, prior: Double?): Double? =
        if (latest != null && prior != null) latest - prior else null

    private fun trend(latest: Double?, prior: Double?, yoy: Double?): String? = when {
        latest == null || prior == null -> null
        latest > prior && (yoy == null || yoy >= 0.0) -> "IMPROVING"
        latest < prior && (yoy == null || yoy < 0.0) -> "DETERIORATING"
        else -> "MIXED"
    }

    private fun rawNumber(parent: JSONObject, key: String): Double? {
        val wrapped = parent.optJSONObject(key)
        if (wrapped != null && wrapped.has("raw") && !wrapped.isNull("raw")) {
            return wrapped.optDouble("raw").takeIf { it.isFinite() }
        }
        return if (parent.has(key) && !parent.isNull(key)) parent.optDouble(key).takeIf { it.isFinite() } else null
    }

    private fun rawDouble(parent: JSONObject, key: String): Double? = rawNumber(parent, key)

    private fun rawLong(parent: JSONObject, key: String): Long? {
        val wrapped = parent.optJSONObject(key)
        if (wrapped != null && wrapped.has("raw") && !wrapped.isNull("raw")) {
            return wrapped.optLong("raw").takeIf { it > 0L }
        }
        return if (parent.has(key) && !parent.isNull(key)) parent.optLong(key).takeIf { it > 0L } else null
    }

    private fun yahooTicker(ticker: String): String {
        val normalized = ticker.trim().uppercase()
        return if (normalized == "DX-Y.NYB") normalized else normalized.replace(".", "-")
    }

    private fun JSONObject.optNullableDouble(key: String): Double? =
        if (has(key) && !isNull(key)) optDouble(key).takeIf { it.isFinite() && it > 0.0 } else null

    private fun JSONObject.optNullableLong(key: String): Long? =
        if (has(key) && !isNull(key)) optLong(key).takeIf { it > 0L } else null

    companion object {
        private const val CACHE_MAX_AGE_MS = 72L * 60 * 60 * 1000
        const val MAX_OPTION_EXPIRIES = 3
    }
}
