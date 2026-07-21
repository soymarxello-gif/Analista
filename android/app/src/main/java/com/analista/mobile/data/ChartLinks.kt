package com.analista.mobile.data

import java.net.URLEncoder
import java.nio.charset.StandardCharsets

object ChartLinks {
    const val VERSION = "chart-links-1"

    fun tradingView(symbol: String, exchange: String?): String {
        val ticker = symbol.trim().uppercase().replace('.', '-')
        require(ticker.isNotBlank())
        val venue = exchange?.trim()?.uppercase()?.takeIf { it.isNotBlank() }
        val qualified = venue?.let { "$it:$ticker" } ?: ticker
        return "https://www.tradingview.com/chart/?symbol=" +
            URLEncoder.encode(qualified, StandardCharsets.UTF_8.toString())
    }
}
