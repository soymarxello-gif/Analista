package com.analista.mobile.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class InstitutionalContrarianEngineTest {
    private fun options(
        score: Double = 35.0,
        bias: String = "BEARISH_WITH_DATA"
    ) = OptionMetricsEngine.Assessment(
        status = "AVAILABLE_COMPLETE",
        coveragePct = 100.0,
        putCallOiTotal = 1.4,
        putCallOiNearSpot = 1.6,
        callWallStrike = 110.0,
        putWallStrike = 95.0,
        callWallDistancePct = 10.0,
        putWallDistancePct = -5.0,
        oiConcentrationPct = 40.0,
        volumeToOiRatio = 0.2,
        ivSkewPutMinusCall = 0.1,
        gammaStatus = "UNKNOWN",
        bias = bias,
        score = score,
        reasons = listOf("fixture")
    )

    private fun component(score: Double?, status: String = "AVAILABLE") =
        InstitutionalContrarianEngine.Component(score, status)

    @Test
    fun highCoverageAdverseFlowCanBlockPriceSignal() {
        val result = InstitutionalContrarianEngine.assess(
            InstitutionalContrarianEngine.Input(
                options = options(),
                volumeAccumulation = component(25.0),
                insiders = component(45.0),
                futuresPositioning = component(40.0),
                bullishConsensusPercentile = 70.0,
                priceTrendConstructive = true,
                technicalScore = 85.0
            )
        )
        assertEquals("HIGH", result.conflict)
        assertTrue(result.coveragePct >= 99.0)
        assertTrue("institutional_conflict_high" in result.reasons)
    }

    @Test
    fun crowdedBullishConsensusReducesInstitutionalProbability() {
        val result = InstitutionalContrarianEngine.assess(
            InstitutionalContrarianEngine.Input(
                options = options(score = 70.0, bias = "CROWDED_BULLISH"),
                volumeAccumulation = component(65.0),
                insiders = component(null, "UNKNOWN"),
                futuresPositioning = component(null, "UNKNOWN"),
                bullishConsensusPercentile = 95.0,
                priceTrendConstructive = true,
                technicalScore = 90.0
            )
        )
        assertEquals(-15.0, result.contrarianAdjustment, 0.0)
        assertTrue(result.adjustedInstitutionalScore < result.institutionalCompositeScore)
        assertTrue("consensus_extreme_bullish" in result.reasons)
    }

    @Test
    fun missingInstitutionalInputsLowerCoverageWithoutInventingNeutrality() {
        val result = InstitutionalContrarianEngine.assess(
            InstitutionalContrarianEngine.Input(
                options = null,
                volumeAccumulation = component(null, "UNKNOWN"),
                insiders = component(null, "UNKNOWN"),
                futuresPositioning = component(null, "UNKNOWN"),
                priceTrendConstructive = true,
                technicalScore = 75.0
            )
        )
        assertEquals("UNKNOWN", result.coverageStatus)
        assertEquals("UNKNOWN_OPTIONS_FLOW", result.optionsBias)
        assertEquals(0.0, result.coveragePct, 0.0)
        assertTrue("options_unknown_not_neutral" in result.reasons)
    }
}
