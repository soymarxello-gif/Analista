package com.analista.mobile.domain

import com.analista.mobile.data.RunUniverseRegistry
import com.analista.mobile.data.UniverseObservationRegistry

object LiveUniverseSnapshotAssembler {
    const val VERSION = "live-universe-assembler-1"

    data class Result(
        val universe: List<String>,
        val bundle: UniverseSelectionEngine.SnapshotBundle
    )

    fun assemble(
        runId: String,
        fallbackUniverse: List<String>,
        effectiveDate: String,
        createdAtUtc: Long
    ): Result {
        require(runId.isNotBlank())
        require(fallbackUniverse.isNotEmpty())
        val universe = RunUniverseRegistry.get(runId)
            ?: fallbackUniverse.map { it.trim().uppercase().replace(".", "-") }
                .filter { it.isNotBlank() }.distinct().sorted()
        val inputs = UniverseObservationRegistry.inputsFor(universe, createdAtUtc)
        val bundle = UniverseSelectionEngine.createSnapshot(
            effectiveDate = effectiveDate,
            inputs = inputs,
            source = "SCAN_RUNTIME",
            createdAtUtc = createdAtUtc
        )
        return Result(universe, bundle)
    }
}
