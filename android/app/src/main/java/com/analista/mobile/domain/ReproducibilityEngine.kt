package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import java.security.MessageDigest
import java.util.Locale

object ReproducibilityEngine {
    const val VERSION = "reproducibility-1"

    data class Manifest(
        val barsHash: String,
        val configurationHash: String,
        val universeHash: String,
        val manifestHash: String,
        val barCount: Int,
        val firstBarEpochSeconds: Long?,
        val lastBarEpochSeconds: Long?
    )

    fun createManifest(
        bars: List<PriceBar>,
        configuration: Map<String, String>,
        universe: List<String>
    ): Manifest {
        val normalizedBars = bars.sortedBy { it.epochSeconds }
        val barsPayload = normalizedBars.joinToString("\n") { bar ->
            listOf(
                bar.epochSeconds.toString(),
                decimal(bar.open),
                decimal(bar.high),
                decimal(bar.low),
                decimal(bar.close),
                bar.volume.toString()
            ).joinToString("|")
        }
        val configurationPayload = configuration.toSortedMap().entries
            .joinToString("\n") { (key, value) -> "${escape(key)}=${escape(value)}" }
        val universePayload = universe.map { it.trim().uppercase(Locale.US) }
            .filter { it.isNotBlank() }
            .distinct()
            .sorted()
            .joinToString("\n")

        val barsHash = sha256(barsPayload)
        val configurationHash = sha256(configurationPayload)
        val universeHash = sha256(universePayload)
        val manifestHash = sha256(listOf(VERSION, barsHash, configurationHash, universeHash).joinToString("|"))
        return Manifest(
            barsHash = barsHash,
            configurationHash = configurationHash,
            universeHash = universeHash,
            manifestHash = manifestHash,
            barCount = normalizedBars.size,
            firstBarEpochSeconds = normalizedBars.firstOrNull()?.epochSeconds,
            lastBarEpochSeconds = normalizedBars.lastOrNull()?.epochSeconds
        )
    }

    private fun decimal(value: Double): String = String.format(Locale.US, "%.8f", value)

    private fun escape(value: String): String = value
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("=", "\\=")

    private fun sha256(value: String): String = MessageDigest.getInstance("SHA-256")
        .digest(value.toByteArray(Charsets.UTF_8))
        .joinToString("") { byte -> "%02x".format(byte) }
}
