package com.analista.mobile.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ScanReproducibilityPolicyTest {
    @Test
    fun `normaliza configuración procedencia y calendario`() {
        val result = ScanReproducibilityPolicy.resolve(
            ScanReproducibilityPolicy.RuntimeInput(
                dataQualityStatus = " high ",
                cacheHit = false,
                retries = 0
            ),
            retrievedAtUtc = 1_700_100_000_000L
        )

        assertEquals("1.0000", result.configuration["riskPct"])
        assertEquals("2.0000", result.configuration["minRiskReward"])
        assertEquals(NyseSessionCalendar.VERSION, result.configuration["calendarVersion"])
        assertEquals("HIGH", result.source.providerStatus)
        assertEquals("YAHOO", result.source.provider)
        assertFalse(result.source.fallbackUsed)
    }

    @Test
    fun `reintento queda registrado como fallback degradado`() {
        val result = ScanReproducibilityPolicy.resolve(
            ScanReproducibilityPolicy.RuntimeInput(
                dataQualityStatus = "LOW",
                cacheHit = true,
                retries = 2
            ),
            retrievedAtUtc = 1_700_100_000_000L
        )

        assertTrue(result.source.fallbackUsed)
        assertTrue(result.source.cacheHit)
        assertEquals("LOW", result.source.providerStatus)
    }

    @Test(expected = IllegalArgumentException::class)
    fun `rechaza timestamp inválido`() {
        ScanReproducibilityPolicy.resolve(
            ScanReproducibilityPolicy.RuntimeInput("HIGH", false, 0),
            retrievedAtUtc = 0L
        )
    }
}
