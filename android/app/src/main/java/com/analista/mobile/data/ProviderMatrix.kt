package com.analista.mobile.data

import java.util.concurrent.ConcurrentHashMap

data class ProviderObservation(
    val module: String,
    val ticker: String?,
    val provider: String,
    val host: String,
    val status: String,
    val coveragePct: Double,
    val providerTimestampUtc: Long?,
    val retrievedAtUtc: Long,
    val freshness: String,
    val fallbackUsed: Boolean,
    val errorStatus: String? = null
)

object ProviderMatrixPolicy {
    const val VERSION = "provider-matrix-1"

    val priorities: Map<String, List<String>> = linkedMapOf(
        "EXECUTION_QUOTE" to listOf("ALPACA", "YAHOO"),
        "HISTORICAL_PRICE" to listOf("ALPACA", "YAHOO"),
        "FUNDAMENTAL" to listOf("YAHOO", "FINVIZ", "MARKETWATCH", "TRADINGVIEW"),
        "OPTIONS" to listOf("YAHOO"),
        "MACRO" to listOf("YAHOO", "OFFICIAL"),
        "CALENDAR" to listOf("LOCAL_XNYS", "OFFICIAL")
    )

    fun validate(observation: ProviderObservation): ProviderObservation {
        require(observation.module in priorities.keys)
        require(observation.provider.isNotBlank())
        require(observation.host.isNotBlank())
        require(observation.status in setOf(
            "AVAILABLE_COMPLETE", "AVAILABLE_PARTIAL", "EMPTY", "STALE", "UNAVAILABLE", "ERROR"
        ))
        require(observation.coveragePct in 0.0..100.0)
        require(observation.retrievedAtUtc > 0L)
        return observation
    }
}

object ProviderMatrixRegistry {
    private val rows = ConcurrentHashMap<String, ProviderObservation>()

    fun record(observation: ProviderObservation) {
        val validated = ProviderMatrixPolicy.validate(observation)
        rows[key(validated.module, validated.ticker)] = validated
    }

    fun get(module: String, ticker: String? = null): ProviderObservation? = rows[key(module, ticker)]

    fun snapshot(): List<ProviderObservation> = rows.values.sortedWith(
        compareBy<ProviderObservation>({ it.module }, { it.ticker.orEmpty() }, { it.provider })
    )

    fun clear() = rows.clear()

    private fun key(module: String, ticker: String?) = "${module.trim().uppercase()}|${ticker?.trim()?.uppercase().orEmpty()}"
}

object ProviderMatrixAssembler {
    fun forTicker(ticker: String, retrievedAtUtc: Long): List<ProviderObservation> {
        require(ticker.isNotBlank())
        require(retrievedAtUtc > 0L)
        val normalized = ticker.trim().uppercase().replace(".", "-")
        val historySource = HistorySourceRegistry.get(normalized)
        val optionChain = OptionChainRegistry.get(normalized)
        val fundamental = FundamentalSnapshotRegistry.get(normalized)
        val rows = mutableListOf<ProviderObservation>()
        rows += historyObservation(normalized, historySource, retrievedAtUtc)
        rows += fundamentalObservation(normalized, fundamental, retrievedAtUtc)
        rows += optionsObservation(normalized, optionChain, retrievedAtUtc)
        return rows.map(ProviderMatrixPolicy::validate)
    }

    private fun historyObservation(ticker: String, source: String?, retrievedAtUtc: Long): ProviderObservation {
        val host = when {
            source?.contains("query2") == true -> "query2.finance.yahoo.com"
            source?.contains("cache") == true -> "local-cache"
            else -> "query1.finance.yahoo.com"
        }
        val available = source != null
        return ProviderObservation(
            module = "HISTORICAL_PRICE",
            ticker = ticker,
            provider = "YAHOO",
            host = host,
            status = if (available) "AVAILABLE_COMPLETE" else "UNAVAILABLE",
            coveragePct = if (available) 100.0 else 0.0,
            providerTimestampUtc = null,
            retrievedAtUtc = retrievedAtUtc,
            freshness = if (source?.contains("cache") == true) "STALE_POSSIBLE" else if (available) "FRESH" else "UNKNOWN",
            fallbackUsed = source?.contains("query2") == true || source?.contains("cache") == true,
            errorStatus = if (available) null else "NO_HISTORY_SOURCE"
        )
    }

    private fun fundamentalObservation(
        ticker: String,
        snapshot: FundamentalSnapshotRegistry.Snapshot?,
        retrievedAtUtc: Long
    ): ProviderObservation {
        val available = snapshot != null
        return ProviderObservation(
            module = "FUNDAMENTAL",
            ticker = ticker,
            provider = "YAHOO",
            host = "query1.finance.yahoo.com",
            status = if (available) "AVAILABLE_PARTIAL" else "UNAVAILABLE",
            coveragePct = if (available) 60.0 else 0.0,
            providerTimestampUtc = snapshot?.capturedAtUtc,
            retrievedAtUtc = retrievedAtUtc,
            freshness = if (available) "ASSESSED_BY_DATA_AGE" else "UNKNOWN",
            fallbackUsed = false,
            errorStatus = if (available) null else "YAHOO_UNAVAILABLE;FINVIZ_NOT_CONFIGURED;MARKETWATCH_NOT_CONFIGURED;TRADINGVIEW_NOT_CONFIGURED"
        )
    }

    private fun optionsObservation(
        ticker: String,
        chain: OptionChainSnapshot?,
        retrievedAtUtc: Long
    ): ProviderObservation {
        val assessment = chain?.let { com.analista.mobile.domain.OptionMetricsEngine.assess(it) }
        return ProviderObservation(
            module = "OPTIONS",
            ticker = ticker,
            provider = chain?.provider ?: "YAHOO",
            host = chain?.providerHost ?: "query2.finance.yahoo.com",
            status = assessment?.status ?: "UNAVAILABLE",
            coveragePct = assessment?.coveragePct ?: 0.0,
            providerTimestampUtc = chain?.capturedAtUtc,
            retrievedAtUtc = retrievedAtUtc,
            freshness = if (chain != null) "SNAPSHOT" else "UNKNOWN",
            fallbackUsed = false,
            errorStatus = if (chain == null) "OPTIONS_UNAVAILABLE" else null
        )
    }
}
