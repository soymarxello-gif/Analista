package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CanonicalEngineConfigurationTest {
    @Test
    fun containsEveryV3DecisionLayerAndIsSorted() {
        val configuration = resolve().configuration
        assertTrue(configuration.size >= 100)
        assertEquals(configuration.keys.sorted(), configuration.keys.toList())
        val required = setOf(
            "strategyDirection",
            "minimumPrice",
            "minimumMarketCapUsd",
            "quoteFreshSeconds",
            "rsiCanonicalPeriod",
            "atrSmoothing",
            "breakoutBufferAtr",
            "setupClassifierVersion",
            "aggressiveStopMinimumRiskReward",
            "macroHorizonsSessions",
            "fundamentalAssessmentVersion",
            "optionNearSpotWindowPct",
            "institutionalContrarianVersion",
            "minimumConfirmedFinalScore",
            "backtestEntrySlippageBps",
            "walkForwardMinimumOutOfSampleClosed",
            "rankingPromotionMinimumExpectancyImprovementR",
            "calendarVersion",
            "normalizedDatasetCodecVersion",
            "liveDatasetCaptureVersion"
        )
        assertTrue(configuration.keys.containsAll(required))
    }

    @Test
    fun sameInputsProduceIdenticalHashes() {
        val first = ReproducibilityEngine.createManifest(bars(), resolve().configuration, listOf("BBB", "AAA"))
        val second = ReproducibilityEngine.createManifest(bars(), resolve().configuration, listOf("AAA", "BBB"))
        assertEquals(first.configurationHash, second.configurationHash)
        assertEquals(first.universeHash, second.universeHash)
        assertEquals(first.manifestHash, second.manifestHash)
    }

    @Test
    fun changingAParameterChangesHashes() {
        val baseline = resolve(minRiskReward = 2.0)
        val changed = resolve(minRiskReward = 3.0)
        assertNotEquals(baseline.configuration, changed.configuration)
        val first = ReproducibilityEngine.createManifest(bars(), baseline.configuration, listOf("AAA"))
        val second = ReproducibilityEngine.createManifest(bars(), changed.configuration, listOf("AAA"))
        assertNotEquals(first.configurationHash, second.configurationHash)
        assertNotEquals(first.manifestHash, second.manifestHash)
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsUnsupportedTargetHorizon() {
        ScanReproducibilityPolicy.resolve(
            ScanReproducibilityPolicy.RuntimeInput(
                dataQualityStatus = "HIGH",
                cacheHit = false,
                retries = 0,
                targetSessions = 30
            ),
            retrievedAtUtc = 1L
        )
    }

    private fun resolve(minRiskReward: Double = 2.0) = ScanReproducibilityPolicy.resolve(
        ScanReproducibilityPolicy.RuntimeInput(
            dataQualityStatus = "HIGH",
            cacheHit = false,
            retries = 0,
            minRiskReward = minRiskReward
        ),
        retrievedAtUtc = 1L
    )

    private fun bars(): List<PriceBar> = (1L..60L).map { index ->
        val close = 100.0 + index
        PriceBar(index, close - 1.0, close + 1.0, close - 2.0, close, 1_000_000L)
    }
}
