package com.analista.mobile.domain

import com.analista.mobile.data.ReproducibilityManifestEntity
import com.analista.mobile.data.RunDefinitionEntity

object RunDefinitionFactory {
    const val VERSION = "run-definition-factory-1"

    fun create(
        runId: String,
        universeName: String,
        universeVersion: String,
        universe: List<String>,
        configurationVersion: String,
        configuration: Map<String, String>,
        engineBundleVersion: String,
        manifests: List<ReproducibilityManifestEntity>,
        createdAtUtc: Long
    ): RunDefinitionEntity {
        require(runId.isNotBlank())
        require(universeName.isNotBlank())
        require(universeVersion.isNotBlank())
        require(configurationVersion.isNotBlank())
        require(engineBundleVersion.isNotBlank())
        require(createdAtUtc > 0L)
        require(manifests.isNotEmpty())
        require(manifests.all { it.runId == runId })

        val normalizedUniverse = universe.map { it.trim().uppercase() }
            .filter { it.isNotBlank() }
            .distinct()
            .sorted()
        require(normalizedUniverse.isNotEmpty())

        val universeHashes = manifests.map { it.universeHash }.toSet()
        val configurationHashes = manifests.map { it.configurationHash }.toSet()
        require(universeHashes.size == 1)
        require(configurationHashes.size == 1)

        val configurationJson = configuration.toSortedMap().entries.joinToString(
            prefix = "{",
            postfix = "}",
            separator = ","
        ) { (key, value) -> "\"${escape(key)}\":\"${escape(value)}\"" }

        return RunDefinitionEntity(
            definitionId = "$runId-definition",
            runId = runId,
            universeName = universeName.trim(),
            universeVersion = universeVersion.trim(),
            universeSymbolsCsv = normalizedUniverse.joinToString(","),
            universeHash = universeHashes.single(),
            configurationVersion = configurationVersion.trim(),
            configurationJson = configurationJson,
            configurationHash = configurationHashes.single(),
            engineBundleVersion = "$engineBundleVersion+$VERSION",
            createdAtUtc = createdAtUtc
        )
    }

    private fun escape(value: String): String = value
        .replace("\\", "\\\\")
        .replace("\"", "\\\"")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
}
