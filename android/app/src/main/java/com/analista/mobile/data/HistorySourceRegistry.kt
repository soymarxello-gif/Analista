package com.analista.mobile.data

import java.util.concurrent.ConcurrentHashMap

object HistorySourceRegistry {
    private val sources = ConcurrentHashMap<String, String>()

    fun record(ticker: String, source: String) {
        val normalizedTicker = normalizeTicker(ticker)
        require(normalizedTicker.isNotBlank())
        require(source.isNotBlank())
        sources[normalizedTicker] = source.trim()
    }

    fun sourceFor(ticker: String): String? = sources[normalizeTicker(ticker)]

    internal fun clear() = sources.clear()

    private fun normalizeTicker(ticker: String): String = ticker.trim().uppercase().replace(".", "-")
}
