package com.analista.mobile.domain

import com.analista.mobile.data.ScanCandidate

object InsiderScanSelectionPolicy {
    const val VERSION = "insider-scan-selection-1"

    fun select(candidates: List<ScanCandidate>, maxTickers: Int = 8): List<String> {
        require(maxTickers in 1..20)
        return candidates.asSequence()
            .filter { it.signal !in setOf("VETO", "AVOID") }
            .filter { it.setupType != "NO_VALID_SETUP" }
            .filter { it.allVetoReasons.isEmpty() }
            .sortedByDescending { it.score }
            .map { it.ticker.trim().uppercase().replace('.', '-') }
            .filter(String::isNotBlank)
            .distinct()
            .take(maxTickers)
            .toList()
    }
}
