package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import com.analista.mobile.data.ReproducibilityManifestEntity

object ReproducibilityManifestFactory {
    const val VERSION = "manifest-factory-1"

    data class SourceMetadata(
        val provider: String,
        val providerHost: String,
        val providerStatus: String,
        val fallbackUsed: Boolean,
        val cacheHit: Boolean,
        val retrievedAtUtc: Long
    )

    data class Input(
        val runId: String,
        val ticker: String,
        val bars: List<PriceBar>,
        val configuration: Map<String, String>,
        val universe: List<String>,
        val source: SourceMetadata
    )

    fun create(input: Input): ReproducibilityManifestEntity {
        require(input.runId.isNotBlank()) { "runId vacío" }
        require(input.ticker.isNotBlank()) { "ticker vacío" }
        require(input.bars.isNotEmpty()) { "barras vacías" }
        val manifest = ReproducibilityEngine.createManifest(
            bars = input.bars,
            configuration = input.configuration,
            universe = input.universe
        )
        val ticker = input.ticker.trim().uppercase()
        return ReproducibilityManifestEntity(
            manifestId = "${input.runId}-$ticker",
            runId = input.runId,
            ticker = ticker,
            barsHash = manifest.barsHash,
            configurationHash = manifest.configurationHash,
            universeHash = manifest.universeHash,
            manifestHash = manifest.manifestHash,
            barCount = manifest.barCount,
            firstBarEpochSeconds = manifest.firstBarEpochSeconds,
            lastBarEpochSeconds = manifest.lastBarEpochSeconds,
            provider = input.source.provider,
            providerHost = input.source.providerHost,
            providerStatus = input.source.providerStatus,
            fallbackUsed = input.source.fallbackUsed,
            cacheHit = input.source.cacheHit,
            retrievedAtUtc = input.source.retrievedAtUtc,
            engineVersion = "${ReproducibilityEngine.VERSION}+$VERSION"
        )
    }

    fun createAll(inputs: List<Input>): List<ReproducibilityManifestEntity> =
        inputs.map(::create).sortedBy { it.ticker }
}
