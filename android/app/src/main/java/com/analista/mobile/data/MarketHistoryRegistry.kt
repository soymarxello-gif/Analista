package com.analista.mobile.data

import java.util.concurrent.ConcurrentHashMap

object MarketHistoryRegistry {
    private val histories = ConcurrentHashMap<String, List<PriceBar>>()

    fun record(symbol: String, bars: List<PriceBar>) {
        val normalized = symbol.trim().uppercase().replace(".", "-")
        if (normalized.isNotEmpty() && bars.isNotEmpty()) histories[normalized] = bars.toList()
    }

    fun get(symbol: String): List<PriceBar>? =
        histories[symbol.trim().uppercase().replace(".", "-")]?.toList()

    fun snapshot(symbols: Collection<String>): Map<String, List<PriceBar>> = symbols.mapNotNull { symbol ->
        get(symbol)?.let { symbol.trim().uppercase().replace(".", "-") to it }
    }.toMap()

    fun clear() = histories.clear()
}
