package com.analista.mobile.data

import java.util.concurrent.ConcurrentHashMap

object SecurityMetadataRegistry {
    data class Metadata(
        val ticker: String,
        val marketCap: Long?,
        val quoteType: String?,
        val sector: String?,
        val industry: String?,
        val source: String,
        val capturedAtUtc: Long
    )

    private val values = ConcurrentHashMap<String, Metadata>()

    fun record(metadata: Metadata) {
        val ticker = normalize(metadata.ticker)
        if (ticker.isBlank() || metadata.capturedAtUtc <= 0L) return
        values[ticker] = metadata.copy(ticker = ticker)
    }

    fun recordAll(metadata: Iterable<Metadata>) = metadata.forEach(::record)

    fun get(ticker: String): Metadata? = values[normalize(ticker)]

    fun clear() = values.clear()

    private fun normalize(ticker: String) = ticker.trim().uppercase().replace('.', '-')
}
