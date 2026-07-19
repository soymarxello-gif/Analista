package com.analista.mobile.domain

import com.analista.mobile.data.ReproducibilityManifestEntity
import com.analista.mobile.data.RunDefinitionEntity

object LiveRunDefinitionAssembler {
    const val VERSION = "live-run-definition-1"
    private const val UNIVERSE_NAME = "scan-universe"
    private const val UNIVERSE_SCHEMA_VERSION = "universe-1"
    private const val CONFIGURATION_SCHEMA_VERSION = "scan-config-1"

    fun assemble(
        runId: String,
        universe: List<String>,
        manifests: List<ReproducibilityManifestEntity>,
        engineBundleVersion: String,
        createdAtUtc: Long
    ): RunDefinitionEntity {
        require(manifests.isNotEmpty())
        val universeHash = manifests.map { it.universeHash }.distinct().single()
        val configurationHash = manifests.map { it.configurationHash }.distinct().single()
        val baseConfiguration = ScanReproducibilityPolicy.resolve(
            ScanReproducibilityPolicy.RuntimeInput(
                dataQualityStatus = "AVAILABLE",
                cacheHit = false,
                retries = 0
            ),
            retrievedAtUtc = 1L
        ).configuration
        val configuration = baseConfiguration + ("assemblerVersion" to LiveReproducibilityAssembler.VERSION)

        return RunDefinitionFactory.create(
            runId = runId,
            universeName = UNIVERSE_NAME,
            universeVersion = "$UNIVERSE_SCHEMA_VERSION:${universeHash.take(12)}",
            universe = universe,
            configurationVersion = "$CONFIGURATION_SCHEMA_VERSION:${configurationHash.take(12)}",
            configuration = configuration,
            engineBundleVersion = "$engineBundleVersion+$VERSION",
            manifests = manifests,
            createdAtUtc = createdAtUtc
        )
    }
}
