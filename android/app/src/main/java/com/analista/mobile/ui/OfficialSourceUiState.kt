package com.analista.mobile.ui

import com.analista.mobile.data.OfficialSourceCoordinator
import com.analista.mobile.data.OfficialSourceSettingsStore

data class OfficialSourceUiState(
    val fredConfigured: Boolean,
    val secConfigured: Boolean,
    val fredSeriesCount: Int = 0,
    val cboeAvailable: Boolean = false,
    val cftcMarketsCount: Int = 0,
    val secTickerCount: Int = 0,
    val status: String = "NO_PROBADO",
    val refreshedAtUtc: Long? = null
) {
    companion object {
        fun fromSettings(settings: OfficialSourceSettingsStore.Settings) = OfficialSourceUiState(
            fredConfigured = !settings.fredApiKey.isNullOrBlank(),
            secConfigured = !settings.secContactEmail.isNullOrBlank()
        )

        fun fromResult(
            settings: OfficialSourceSettingsStore.Settings,
            result: OfficialSourceCoordinator.Result
        ) = OfficialSourceUiState(
            fredConfigured = !settings.fredApiKey.isNullOrBlank(),
            secConfigured = !settings.secContactEmail.isNullOrBlank(),
            fredSeriesCount = result.fredSeriesCount,
            cboeAvailable = result.cboeAvailable,
            cftcMarketsCount = result.cftcMarketsCount,
            secTickerCount = result.secTickerCount,
            status = when {
                result.cboeAvailable && result.cftcMarketsCount > 0 &&
                    (!settings.fredApiKey.isNullOrBlank()).implies(result.fredSeriesCount > 0) &&
                    (!settings.secContactEmail.isNullOrBlank()).implies(result.secTickerCount > 0) -> "AVAILABLE"
                result.cboeAvailable || result.cftcMarketsCount > 0 || result.fredSeriesCount > 0 || result.secTickerCount > 0 -> "PARTIAL"
                else -> "UNAVAILABLE"
            },
            refreshedAtUtc = result.refreshedAtUtc
        )

        private fun Boolean.implies(value: Boolean): Boolean = !this || value
    }
}
