package com.analista.mobile.data

import java.util.concurrent.ConcurrentHashMap

object MarketHistoryRegistry {
    private val histories = ConcurrentHashMap<String, List<PriceBar>>()

    fun record(symbol: String, bars: List<PriceBar>) {
        val normalized = canonical(symbol)
        if (normalized.isNotEmpty() && bars.isNotEmpty()) histories[normalized] = bars.toList()
    }

    fun get(symbol: String): List<PriceBar>? = histories[canonical(symbol)]?.toList()

    fun snapshot(symbols: Collection<String>): Map<String, List<PriceBar>> = symbols.mapNotNull { symbol ->
        get(symbol)?.let { canonical(symbol) to it }
    }.toMap()

    fun clear() = histories.clear()

    private fun canonical(symbol: String): String = symbol.trim().uppercase()
}
