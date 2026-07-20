package com.analista.mobile.data

import java.util.concurrent.ConcurrentHashMap

object FundamentalSnapshotRegistry {
    data class Snapshot(
        val ticker: String,
        val metrics: FundamentalMetrics,
        val capturedAtUtc: Long
    )

    private val snapshots = ConcurrentHashMap<String, Snapshot>()

    fun record(ticker: String, metrics: FundamentalMetrics, capturedAtUtc: Long = System.currentTimeMillis()) {
        val normalized = ticker.trim().uppercase().replace(".", "-")
        if (normalized.isNotEmpty()) snapshots[normalized] = Snapshot(normalized, metrics, capturedAtUtc)
    }

    fun get(ticker: String): Snapshot? = snapshots[ticker.trim().uppercase().replace(".", "-")]

    fun clear() = snapshots.clear()
}
