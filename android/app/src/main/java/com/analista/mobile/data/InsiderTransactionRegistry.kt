package com.analista.mobile.data

import java.util.concurrent.ConcurrentHashMap

object InsiderTransactionRegistry {
    data class Snapshot(
        val ticker: String,
        val transactions: List<SecEdgarClient.InsiderTransaction>,
        val status: String,
        val capturedAtUtc: Long,
        val provider: String = "SEC_EDGAR"
    )

    private val entries = ConcurrentHashMap<String, Snapshot>()

    fun record(snapshot: Snapshot) {
        val ticker = normalize(snapshot.ticker)
        require(ticker.isNotBlank()) { "ticker is required" }
        require(snapshot.capturedAtUtc > 0L) { "capturedAtUtc must be positive" }
        entries[ticker] = snapshot.copy(
            ticker = ticker,
            transactions = snapshot.transactions.filter { row ->
                row.ticker == null || normalize(row.ticker) == ticker
            }
        )
    }

    fun get(ticker: String): Snapshot? = entries[normalize(ticker)]

    fun snapshot(): Map<String, Snapshot> = entries.toSortedMap()

    fun clear() = entries.clear()

    private fun normalize(value: String): String = value.trim().uppercase().replace('.', '-')
}
