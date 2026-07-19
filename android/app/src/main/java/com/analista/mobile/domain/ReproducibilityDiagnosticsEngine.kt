package com.analista.mobile.domain

import com.analista.mobile.data.ReproducibilityManifestEntity

object ReproducibilityDiagnosticsEngine {
    const val VERSION = "repro-diagnostics-1"

    data class Summary(
        val expectedTickers: Int,
        val manifestCount: Int,
        val coveragePct: Double,
        val uniqueConfigurationHashes: Int,
        val uniqueUniverseHashes: Int,
        val providers: Set<String>,
        val fallbackCount: Int,
        val cacheHitCount: Int,
        val invalidManifestCount: Int,
        val status: String
    )

    fun summarize(expectedTickers: Int, manifests: List<ReproducibilityManifestEntity>): Summary {
        require(expectedTickers >= 0) { "expectedTickers negativo" }
        val uniqueByTicker = manifests.distinctBy { it.ticker }
        val coverage = if (expectedTickers == 0) 0.0 else uniqueByTicker.size * 100.0 / expectedTickers
        val invalid = manifests.count {
            it.barsHash.length != 64 || it.configurationHash.length != 64 ||
                it.universeHash.length != 64 || it.manifestHash.length != 64 || it.barCount <= 0
        }
        val configurationHashes = manifests.map { it.configurationHash }.toSet()
        val universeHashes = manifests.map { it.universeHash }.toSet()
        val status = when {
            expectedTickers == 0 -> "NO_EXPECTATION"
            invalid > 0 -> "INVALID"
            coverage < 80.0 -> "INCOMPLETE"
            configurationHashes.size > 1 || universeHashes.size > 1 -> "INCONSISTENT"
            coverage < 100.0 -> "DEGRADED"
            else -> "COMPLETE"
        }
        return Summary(
            expectedTickers = expectedTickers,
            manifestCount = uniqueByTicker.size,
            coveragePct = kotlin.math.round(coverage * 100.0) / 100.0,
            uniqueConfigurationHashes = configurationHashes.size,
            uniqueUniverseHashes = universeHashes.size,
            providers = manifests.map { it.provider }.filter { it.isNotBlank() }.toSortedSet(),
            fallbackCount = manifests.count { it.fallbackUsed },
            cacheHitCount = manifests.count { it.cacheHit },
            invalidManifestCount = invalid,
            status = status
        )
    }
}
