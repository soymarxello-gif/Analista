package com.analista.mobile.data

import java.util.concurrent.ConcurrentHashMap

object DynamicScanRegistry {
    data class State(
        val symbols: List<String>,
        val source: String,
        val status: String,
        val fallbackUsed: Boolean,
        val preparedAtUtc: Long
    )

    @Volatile
    private var state: State? = null
    private val histories = ConcurrentHashMap<String, FetchResult>()

    fun activate(resolution: DynamicUniverseResolver.Resolution, preparedAtUtc: Long = System.currentTimeMillis()) {
        val symbols = resolution.symbols.map(::normalize).filter { it.isNotBlank() }.distinct()
        require(symbols.isNotEmpty())
        histories.clear()
        resolution.histories.forEach { (symbol, result) -> histories[normalize(symbol)] = result }
        state = State(symbols, resolution.source, resolution.status, resolution.fallbackUsed, preparedAtUtc)
    }

    fun clear() {
        state = null
        histories.clear()
    }

    fun state(): State? = state

    fun symbols(fallback: List<String>): List<String> = state?.symbols ?: fallback

    fun history(symbol: String): FetchResult? = histories[normalize(symbol)]

    private fun normalize(symbol: String) = symbol.trim().uppercase().replace('.', '-')
}

class DynamicTickerList(private val fallback: List<String>) : AbstractList<String>() {
    private fun snapshot() = DynamicScanRegistry.symbols(fallback)
    override val size: Int get() = snapshot().size
    override fun get(index: Int): String = snapshot()[index]
}

class DynamicScanCoordinator(
    private val resolver: DynamicUniverseResolver,
    private val emergencySymbols: List<String>,
    private val officialSources: OfficialSourceCoordinator? = null
) {
    suspend fun prepare(): DynamicUniverseResolver.Resolution {
        DynamicScanRegistry.clear()
        officialSources?.refresh()
        val resolution = resolver.resolve(emergencySymbols)
        DynamicScanRegistry.activate(resolution)
        return resolution
    }
}
