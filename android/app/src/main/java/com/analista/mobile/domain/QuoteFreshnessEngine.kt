package com.analista.mobile.domain

import com.analista.mobile.data.MarketQuote
import kotlin.math.max

object QuoteFreshnessEngine {
    const val VERSION = "quote-freshness-2"

    data class Thresholds(
        val freshSeconds: Long = 120L,
        val delayedAcceptableSeconds: Long = 900L,
        val maximumFutureSkewSeconds: Long = 30L
    )

    data class Assessment(
        val status: String,
        val ageSeconds: Long?,
        val marketSession: String,
        val executionSessionOpen: Boolean,
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
        val executionSessionOpen = marketSession in setOf("PREMARKET", "REGULAR")
        val timestamp = quote?.providerTimestampUtc
        if (quote == null || timestamp == null || timestamp <= 0L) {
            return Assessment(
                status = "UNKNOWN",
                ageSeconds = null,
                marketSession = marketSession,
                executionSessionOpen = executionSessionOpen,
                permitsConfirmation = false,
                permitsWaitingContract = false,
                reasons = buildList {
                    add("quote_provider_timestamp_missing")
                    if (!executionSessionOpen) add("market_session_not_executable")
                }
            )
        }

        val rawAgeSeconds = (nowUtcMillis - timestamp) / 1_000L
        if (rawAgeSeconds < -thresholds.maximumFutureSkewSeconds) {
            return Assessment(
                status = "UNKNOWN",
                ageSeconds = rawAgeSeconds,
                marketSession = marketSession,
                executionSessionOpen = executionSessionOpen,
                permitsConfirmation = false,
                permitsWaitingContract = false,
                reasons = buildList {
                    add("quote_timestamp_in_future")
                    if (!executionSessionOpen) add("market_session_not_executable")
                }
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
            executionSessionOpen = executionSessionOpen,
            permitsConfirmation = executionSessionOpen && status == "FRESH",
            permitsWaitingContract = executionSessionOpen && status in setOf("FRESH", "DELAYED_ACCEPTABLE"),
            reasons = buildList {
                when (status) {
                    "DELAYED_ACCEPTABLE" -> add("quote_delayed_acceptable")
                    "STALE" -> add("quote_stale")
                }
                if (!executionSessionOpen) add("market_session_not_executable")
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
