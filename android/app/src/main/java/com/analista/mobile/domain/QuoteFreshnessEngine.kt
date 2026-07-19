package com.analista.mobile.domain

import com.analista.mobile.data.MarketQuote
import kotlin.math.max

object QuoteFreshnessEngine {
    const val VERSION = "quote-freshness-1"

    data class Thresholds(
        val freshMaxAgeSeconds: Long = 120L,
        val delayedMaxAgeSeconds: Long = 900L
    )

    data class Assessment(
        val provider: String,
        val providerTimestampUtc: Long?,
        val retrievedAtUtc: Long?,
        val quoteAgeSeconds: Long?,
        val freshnessStatus: String,
        val marketSession: String,
        val permitsReady: Boolean,
        val permitsConfirmation: Boolean,
        val reasons: List<String>
    )

    fun assess(
        quote: MarketQuote?,
        nowUtcMillis: Long = System.currentTimeMillis(),
        thresholds: Thresholds = Thresholds()
    ): Assessment {
        require(nowUtcMillis > 0L)
        require(thresholds.freshMaxAgeSeconds >= 0L)
        require(thresholds.delayedMaxAgeSeconds >= thresholds.freshMaxAgeSeconds)

        val provider = quote?.provider?.trim()?.uppercase().orEmpty().ifBlank { "UNKNOWN" }
        val providerTimestamp = quote?.providerTimestampUtc
        val age = providerTimestamp?.takeIf { it > 0L }?.let { max(0L, (nowUtcMillis - it) / 1000L) }
        val status = when {
            quote == null || providerTimestamp == null || providerTimestamp <= 0L -> "UNKNOWN"
            age!! <= thresholds.freshMaxAgeSeconds -> "FRESH"
            age <= thresholds.delayedMaxAgeSeconds -> "DELAYED_ACCEPTABLE"
            else -> "STALE"
        }
        val reasons = buildList {
            if (quote == null) add("quote_missing")
            if (providerTimestamp == null || providerTimestamp <= 0L) add("provider_timestamp_missing")
            if (status == "DELAYED_ACCEPTABLE") add("quote_delayed")
            if (status == "STALE") add("quote_stale")
        }
        return Assessment(
            provider = provider,
            providerTimestampUtc = providerTimestamp,
            retrievedAtUtc = quote?.retrievedAtUtc,
            quoteAgeSeconds = age,
            freshnessStatus = status,
            marketSession = quote?.marketState?.trim()?.uppercase().orEmpty().ifBlank { "UNKNOWN" },
            permitsReady = status in setOf("FRESH", "DELAYED_ACCEPTABLE"),
            permitsConfirmation = status == "FRESH",
            reasons = reasons
        )
    }
}