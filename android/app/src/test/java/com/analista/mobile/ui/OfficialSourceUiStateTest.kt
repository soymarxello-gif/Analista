package com.analista.mobile.ui

import com.analista.mobile.data.OfficialSourceCoordinator
import com.analista.mobile.data.OfficialSourceSettingsStore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class OfficialSourceUiStateTest {
    @Test
    fun settingsExposeOnlyConfigurationFlags() {
        val state = OfficialSourceUiState.fromSettings(
            OfficialSourceSettingsStore.Settings("secret", "contact@example.com")
        )

        assertTrue(state.fredConfigured)
        assertTrue(state.secConfigured)
        assertEquals("NO_PROBADO", state.status)
        assertEquals(0, state.fredSeriesCount)
    }

    @Test
    fun completeRefreshIsAvailable() {
        val settings = OfficialSourceSettingsStore.Settings("secret", "contact@example.com")
        val result = OfficialSourceCoordinator.Result(
            fredSeriesCount = 8,
            cboeAvailable = true,
            cftcMarketsCount = 12,
            secTickerCount = 10_000,
            statuses = emptyList(),
            refreshedAtUtc = 100L
        )

        val state = OfficialSourceUiState.fromResult(settings, result)

        assertEquals("AVAILABLE", state.status)
        assertEquals(8, state.fredSeriesCount)
        assertEquals(100L, state.refreshedAtUtc)
    }

    @Test
    fun configuredSourceWithoutCoverageIsPartialWhenPublicSourcesWork() {
        val settings = OfficialSourceSettingsStore.Settings("secret", null)
        val result = OfficialSourceCoordinator.Result(
            fredSeriesCount = 0,
            cboeAvailable = true,
            cftcMarketsCount = 4,
            secTickerCount = 0,
            statuses = emptyList(),
            refreshedAtUtc = 200L
        )

        val state = OfficialSourceUiState.fromResult(settings, result)

        assertEquals("PARTIAL", state.status)
        assertTrue(state.fredConfigured)
        assertFalse(state.secConfigured)
    }

    @Test
    fun emptyRefreshRemainsUnavailable() {
        val state = OfficialSourceUiState.fromResult(
            OfficialSourceSettingsStore.Settings(null, null),
            OfficialSourceCoordinator.Result(0, false, 0, 0, emptyList(), 300L)
        )

        assertEquals("UNAVAILABLE", state.status)
    }
}
