package com.analista.mobile.data

import java.util.concurrent.ConcurrentHashMap

object SourceStatusRegistry {
    const val VERSION = "source-status-1"
    private val values = ConcurrentHashMap<String, SourceStatus>()

    fun record(value: SourceStatus) {
        require(value.module.isNotBlank())
        require(value.provider.isNotBlank())
        require(value.capturedAtUtc > 0L)
        values[value.module.trim().uppercase()] = value.copy(
            module = value.module.trim().uppercase(),
            provider = value.provider.trim().uppercase(),
            detail = value.detail?.take(240)
        )
    }

    fun snapshot(): List<SourceStatus> = values.values.sortedBy { it.module }
    fun get(module: String): SourceStatus? = values[module.trim().uppercase()]
    fun clear() = values.clear()
}
