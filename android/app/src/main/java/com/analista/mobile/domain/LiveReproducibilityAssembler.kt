package com.analista.mobile.domain

import com.analista.mobile.data.HistorySourceRegistry
import com.analista.mobile.data.PriceBar
import com.analista.mobile.data.ReproducibilityManifestEntity

object LiveReproducibilityAssembler {
    const val VERSION = "live-repro-assembler-2"

    data class TickerInput(
        val ticker: String,
        val bars: List<PriceBar>,
        val dataQualityStatus: String,
        val cacheHit: Boolean,
        val retries: Int,
        val retrievedAtUtc: Long
    )

    fun assemble(runId: String, universe: List<String>, inputs: List<TickerInput>): List<ReproducibilityManifestEntity> {
        require(runId.isNotBlank())
        require(universe.isNotEmpty())
        val normalizedUniverse = universe.map { it.trim().uppercase() }.filter { it.isNotBlank() }.distinct().sorted()
        require(normalizedUniverse.isNotEmpty())
        require(inputs.map { it.ticker.trim().uppercase() }.distinct().size == inputs.size)
        return ReproducibilityManifestFactory.createAll(inputs.map { item ->
            val policy = ScanReproducibilityPolicy.resolve(
                ScanReproducibilityPolicy.RuntimeInput(item.dataQualityStatus, item.cacheHit, item.retries),
                item.retrievedAtUtc
            )
            val actualSource = HistorySourceRegistry.sourceFor(item.ticker)
            val actualHost = actualSource
                ?.takeIf { it.startsWith("Yahoo/") }
                ?.removePrefix("Yahoo/")
                ?.takeIf { it.isNotBlank() }
                ?: policy.source.providerHost
            val source = policy.source.copy(
                providerHost = actualHost,
                fallbackUsed = policy.source.fallbackUsed || actualHost == "query2.finance.yahoo.com" || actualHost == "cache",
                cacheHit = item.cacheHit || actualHost == "cache"
            )
            ReproducibilityManifestFactory.Input(
                runId = runId,
                ticker = item.ticker,
                bars = item.bars,
                configuration = policy.configuration + ("assemblerVersion" to VERSION),
                universe = normalizedUniverse,
                source = source
            )
        })
    }
}
