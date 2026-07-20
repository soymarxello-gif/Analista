package com.analista.mobile.domain

import com.analista.mobile.data.OptionChainSnapshot
import com.analista.mobile.data.OptionContractSnapshot
import com.analista.mobile.data.OptionExpirySnapshot
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class OptionAssessmentPersistenceFactoryTest {
    private val chain = OptionChainSnapshot(
        ticker = "TEST",
        spot = 100.0,
        expiries = listOf(
            OptionExpirySnapshot(
                1_800_000_000L,
                listOf(
                    contract("CALL", 100.0, 1_000L, 300L, 0.25, 0.0),
                    contract("PUT", 95.0, 1_500L, 250L, 0.35, -5.0)
                )
            )
        ),
        availableExpiries = listOf(1_800_000_000L),
        capturedAtUtc = 123L,
        provider = "YAHOO",
        providerHost = "query2.finance.yahoo.com",
        gammaStatus = "UNKNOWN"
    )

    private fun contract(type: String, strike: Double, oi: Long, volume: Long, iv: Double, distance: Double) =
        OptionContractSnapshot(
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

    @Test
    fun createsAuditableEntityFromNormalizedChain() {
        val entity = OptionAssessmentPersistenceFactory.create("run", "test", chain, technicalScore = 80.0)
        assertEquals("run-TEST", entity.assessmentId)
        assertEquals("TEST", entity.ticker)
        assertEquals("BEARISH_WITH_DATA", entity.bias)
        assertEquals("UNKNOWN", entity.gammaStatus)
        assertEquals(1.5, entity.putCallOiNearSpot ?: 0.0, 0.0001)
        assertTrue(entity.engineVersion.contains(OptionMetricsEngine.VERSION))
        assertTrue(entity.reasons.contains("institutional_coverage_incomplete"))
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsBlankRunId() {
        OptionAssessmentPersistenceFactory.create("", "TEST", chain)
    }
}
