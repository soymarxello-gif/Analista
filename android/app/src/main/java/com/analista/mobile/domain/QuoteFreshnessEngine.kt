package com.analista.mobile.domain

import com.analista.mobile.data.MarketQuote
import kotlin.math.max

object QuoteFreshnessEngine {
    const val VERSION = "quote-freshness-1"

    data class Thresholds(
        val freshSeconds: Long = 120L,
        val delayedAcceptableSeconds: Long = 900L,
        val maximumFutureSkewSeconds: Long = 30L
    )

    data class Assessment(
        val status: String,
        val ageSeconds: Long?,
        val marketSession: String,
        val permitsConfirmation: Boolean,
        val permitsWaitingContract: Boolean,
        val reasons: List<String>
    )

    fun assess(
        quote: MarketQuote?,
        nowUtcMillis: Long = System.currentTimeMillis(),
        thresholds: Thresholds = Thresholds()
    ): Assessment {
        require(nowUtcMillis > 0L)
        require(thresholds.freshSeconds > 0L)
        require(thresholds.delayedAcceptableSeconds >= thresholds.freshSeconds)
        require(thresholds.maximumFutureSkewSeconds >= 0L)

        val marketSession = normalizeSession(quote?.marketState)
        val timestamp = quote?.providerTimestampUtc
        if (quote == null || timestamp == null || timestamp <= 0L) {
            return Assessment(
                status = "UNKNOWN",
                ageSeconds = null,
                marketSession = marketSession,
                permitsConfirmation = false,
                permitsWaitingContract = false,
                reasons = listOf("quote_provider_timestamp_missing")
            )
        }

        val rawAgeSeconds = (nowUtcMillis - timestamp) / 1_000L
        if (rawAgeSeconds < -thresholds.maximumFutureSkewSeconds) {
            return Assessment(
                status = "UNKNOWN",
                ageSeconds = rawAgeSeconds,
                marketSession = marketSession,
                permitsConfirmation = false,
                permitsWaitingContract = false,
                reasons = listOf("quote_timestamp_in_future")
            )
        }

        val ageSeconds = max(0L, rawAgeSeconds)
        val status = when {
            ageSeconds <= thresholds.freshSeconds -> "FRESH"
            ageSeconds <= thresholds.delayedAcceptableSeconds -> "DELAYED_ACCEPTABLE"
            else -> "STALE"
        }
        return Assessment(
            status = status,
            ageSeconds = ageSeconds,
            marketSession = marketSession,
            permitsConfirmation = status == "FRESH",
            permitsWaitingContract = status in setOf("FRESH", "DELAYED_ACCEPTABLE"),
            reasons = when (status) {
                "DELAYED_ACCEPTABLE" -> listOf("quote_delayed_acceptable")
                "STALE" -> listOf("quote_stale")
                else -> emptyList()
            }
        )
    }

    private fun normalizeSession(raw: String?): String = when (raw?.trim()?.uppercase()) {
        "PRE", "PREPRE" -> "PREMARKET"
        "REGULAR" -> "REGULAR"
        "POST", "POSTPOST" -> "POSTMARKET"
        "CLOSED" -> "CLOSED"
        else -> "UNKNOWN"
    }
}
