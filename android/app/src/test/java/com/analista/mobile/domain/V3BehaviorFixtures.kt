package com.analista.mobile.domain

import com.analista.mobile.data.MarketQuote
import com.analista.mobile.data.PriceBar
import com.analista.mobile.data.TradeContext

internal object V3BehaviorFixtures {
    val requiredScenarios = setOf(
        "valid_breakout",
        "lost_breakout",
        "pullback",
        "excessive_gap",
        "stale_quote",
        "invalid_quote",
        "adverse_macro",
        "deteriorating_fundamentals",
        "bearish_options",
        "sub_one_atr_stop",
        "ambiguous_same_bar_exit"
    )

    fun trendingBars(count: Int = 240, finalVolume: Long = 2_000_000L): List<PriceBar> =
        (0 until count).map { index ->
            val close = 80.0 + index * 0.20 + if (index % 13 == 0) -0.35 else 0.0
            PriceBar(
                epochSeconds = 1_700_000_000L + index * 86_400L,
                open = close - 0.30,
                high = close + 0.90,
                low = close - 0.90,
                close = close,
                volume = if (index == count - 1) finalVolume else 1_000_000L
            )
        }

    fun validQuote(price: Double, capturedAtUtc: Long = 1_800_000_000_000L) = MarketQuote(
        bid = price - 0.05,
        ask = price + 0.05,
        regularMarketPrice = price,
        preMarketPrice = price,
        marketCap = 10_000_000_000L,
        quoteType = "EQUITY",
        marketState = "PRE",
        capturedAtUtc = capturedAtUtc
    )

    fun invalidQuote(price: Double) = MarketQuote(
        bid = price + 0.10,
        ask = price - 0.10,
        regularMarketPrice = price,
        preMarketPrice = price,
        marketCap = 10_000_000_000L,
        quoteType = "EQUITY"
    )

    fun context(quote: MarketQuote, setupType: String = "BREAKOUT_OR_PULLBACK") = TradeContext(
        quote = quote,
        marketCap = quote.marketCap,
        quoteType = quote.quoteType,
        setupType = setupType,
        dataQualityStatus = "HIGH",
        executionDataAllowed = true
    )
}