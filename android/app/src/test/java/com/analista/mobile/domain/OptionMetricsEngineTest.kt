package com.analista.mobile.domain

import com.analista.mobile.data.OptionChainSnapshot
import com.analista.mobile.data.OptionContractSnapshot
import com.analista.mobile.data.OptionExpirySnapshot
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class OptionMetricsEngineTest {
    private fun contract(
        type: String,
        strike: Double,
        oi: Long,
        volume: Long,
        iv: Double,
        distance: Double
    ) = OptionContractSnapshot(
        expiryEpochSeconds = 1_800_000_000L,
        strike = strike,
        type = type,
        bid = 1.0,
        ask = 1.2,
        volume = volume,
        openInterest = oi,
        impliedVolatility = iv,
        delta = null,
        gamma = null,
        distanceToSpotPct = distance,
        lastTradeEpochSeconds = null
    )

    private fun chain(contracts: List<OptionContractSnapshot>) = OptionChainSnapshot(
        ticker = "TEST",
        spot = 100.0,
        expiries = listOf(OptionExpirySnapshot(1_800_000_000L, contracts)),
        availableExpiries = listOf(1_800_000_000L),
        capturedAtUtc = 1L,
        provider = "YAHOO",
        providerHost = "query2.finance.yahoo.com",
        gammaStatus = "UNKNOWN"
    )

    @Test
    fun computesNearSpotRatioWallsAndSkew() {
        val result = OptionMetricsEngine.assess(chain(listOf(
            contract("CALL", 105.0, 1_000, 200, 0.25, 5.0),
            contract("CALL", 120.0, 200, 20, 0.22, 20.0),
            contract("PUT", 95.0, 700, 120, 0.34, -5.0),
            contract("PUT", 80.0, 100, 10, 0.30, -20.0)
        )))
        assertEquals("AVAILABLE_COMPLETE", result.status)
        assertEquals(0.7, result.putCallOiNearSpot ?: 0.0, 0.0001)
        assertEquals(105.0, result.callWallStrike ?: 0.0, 0.0)
        assertEquals(95.0, result.putWallStrike ?: 0.0, 0.0)
        assertTrue((result.ivSkewPutMinusCall ?: 0.0) > 0.0)
        assertEquals("BULLISH_WITH_DATA", result.bias)
        assertEquals("UNKNOWN", result.gammaStatus)
    }

    @Test
    fun detectsCrowdedBullishOnlyWithVolumeAndConcentration() {
        val result = OptionMetricsEngine.assess(chain(listOf(
            contract("CALL", 100.0, 2_000, 900, 0.40, 0.0),
            contract("CALL", 105.0, 200, 100, 0.35, 5.0),
            contract("PUT", 95.0, 500, 100, 0.45, -5.0)
        )))
        assertEquals("CROWDED_BULLISH", result.bias)
        assertTrue("oi_concentration_high" in result.reasons)
    }

    @Test
    fun emptyChainIsUnknownNotNeutral() {
        val result = OptionMetricsEngine.assess(chain(emptyList()))
        assertEquals("EMPTY", result.status)
        assertEquals("UNKNOWN_OPTIONS_FLOW", result.bias)
        assertEquals(50.0, result.score, 0.0)
        assertTrue("options_unknown_not_neutral" in result.reasons)
    }
}
