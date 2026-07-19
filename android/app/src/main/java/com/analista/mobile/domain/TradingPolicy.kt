package com.analista.mobile.domain

import com.analista.mobile.data.MarketQuote

object TradingPolicy {
    const val MIN_PRICE = 10.0
    const val MIN_MARKET_CAP = 1_500_000_000L
    const val MIN_RR = 2.0
    const val MAX_QUOTE_DISTANCE_PCT = 3.0

    val allowedSignals = setOf("VETO", "AVOID", "WATCHLIST", "READY_WAIT_TRIGGER", "TRIGGER_CONFIRMED")
    val excludedQuoteTypes = setOf("ETF", "ETN", "MUTUALFUND", "WARRANT", "PREFERRED", "UNIT", "RIGHT")

    data class QuoteAssessment(val status: String, val quality: String)

    fun assessQuote(quote: MarketQuote?, referencePrice: Double): QuoteAssessment {
        val bid = quote?.bid
        val ask = quote?.ask
        if (bid == null || ask == null) return QuoteAssessment("MISSING", "LOW")
        if (bid <= 0.0 || ask <= 0.0 || ask <= bid) return QuoteAssessment("INVALID", "LOW")
        val midpoint = (bid + ask) / 2.0
        val spreadPct = (ask - bid) / midpoint * 100.0
        val liveAnchor = quote.preMarketPrice ?: quote.regularMarketPrice ?: referencePrice
        val distancePct = if (liveAnchor > 0.0) {
            kotlin.math.abs(midpoint / liveAnchor - 1.0) * 100.0
        } else {
            Double.POSITIVE_INFINITY
        }
        if (distancePct > MAX_QUOTE_DISTANCE_PCT) return QuoteAssessment("STALE_POSSIBLE", "LOW")
        if (spreadPct > 1.0) return QuoteAssessment("WIDE_OR_INCOHERENT", "MEDIUM")
        return QuoteAssessment("VALID", "HIGH")
    }

    fun hardVetoReasons(price: Double, marketCap: Long?, quoteType: String?): List<String> = buildList {
        if (price < MIN_PRICE) add("price_below_min")
        if (marketCap == null || marketCap < MIN_MARKET_CAP) add("market_cap_below_min")
        val normalized = quoteType?.uppercase()
        if (normalized != null && normalized in excludedQuoteTypes) add("excluded_security_type")
    }
}
