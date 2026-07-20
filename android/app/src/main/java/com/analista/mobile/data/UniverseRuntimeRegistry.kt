package com.analista.mobile.data

import com.analista.mobile.domain.UniverseSelectionEngine
import java.util.concurrent.ConcurrentHashMap

object UniverseObservationRegistry {
    const val VERSION = "universe-observation-registry-1"
    private val observations = ConcurrentHashMap<String, UniverseSelectionEngine.Input>()

    fun record(input: UniverseSelectionEngine.Input) {
        val ticker = normalize(input.ticker)
        require(ticker.isNotBlank())
        observations[ticker] = input.copy(ticker = ticker)
    }

    fun get(ticker: String): UniverseSelectionEngine.Input? = observations[normalize(ticker)]

    fun inputsFor(tickers: List<String>, fallbackCapturedAtUtc: Long): List<UniverseSelectionEngine.Input> {
        require(fallbackCapturedAtUtc > 0L)
        return tickers.map { normalize(it) }.filter { it.isNotBlank() }.distinct().sorted().map { ticker ->
            observations[ticker] ?: UniverseSelectionEngine.Input(
                ticker = ticker,
                instrumentType = null,
                price = null,
                marketCap = null,
                averageDollarVolume20 = null,
                spreadPct = null,
                capturedAtUtc = fallbackCapturedAtUtc
            )
        }
    }

    fun clear() = observations.clear()
    private fun normalize(ticker: String) = ticker.trim().uppercase().replace(".", "-")
}

object RunUniverseRegistry {
    const val VERSION = "run-universe-registry-1"
    private val universes = ConcurrentHashMap<String, List<String>>()

    fun record(runId: String, universe: List<String>) {
        require(runId.isNotBlank())
        val normalized = universe.map { it.trim().uppercase().replace(".", "-") }
            .filter { it.isNotBlank() }
            .distinct()
            .sorted()
        require(normalized.isNotEmpty())
        universes[runId] = normalized
    }

    fun get(runId: String): List<String>? = universes[runId]
    fun remove(runId: String): List<String>? = universes.remove(runId)
    fun clear() = universes.clear()
}
