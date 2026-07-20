package com.analista.mobile.domain

import com.analista.mobile.data.CandidateEntity
import com.analista.mobile.data.NormalizedDatasetDecoder
import com.analista.mobile.data.ReproducibilityManifestEntity
import com.analista.mobile.data.RunDefinitionEntity
import com.analista.mobile.data.ScanRunEntity
import com.analista.mobile.data.UniverseMemberEntity
import com.analista.mobile.data.UniverseSnapshotEntity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DeterministicReplayEngineTest {
    @Test
    fun missingBarsProducesIncompleteReplayInsteadOfInventingResults() {
        val result = DeterministicReplayEngine.replay(
            stored = stored(),
            datasets = DeterministicReplayEngine.DatasetBundle(
                barsByTicker = emptyMap(),
                quotesByTicker = emptyMap(),
                macroSnapshots = emptyList(),
                macroHistories = emptyMap(),
                fundamentalsByTicker = emptyMap(),
                optionsByTicker = emptyMap(),
                universe = universe()
            )
        )
        assertEquals("INCOMPLETE", result.status)
        assertEquals(1, result.expectedTickers)
        assertEquals(0, result.replayedTickers)
        assertTrue(result.missingDatasetCount > 0)
        assertTrue("missing_replay_datasets" in result.reasons)
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsRowsFromAnotherRun() {
        val stored = stored().copy(candidates = listOf(candidate(runId = "other")))
        DeterministicReplayEngine.replay(
            stored,
            DeterministicReplayEngine.DatasetBundle(
                emptyMap(), emptyMap(), emptyList(), emptyMap(), emptyMap(), emptyMap(), universe()
            )
        )
    }

    private fun stored() = DeterministicReplayEngine.StoredRun(
        run = ScanRunEntity(
            runId = "run-1",
            startedAtUtc = 1_000L,
            finishedAtUtc = 2_000L,
            marketDateEt = "2026-07-20",
            status = "COMPLETED",
            trustStatus = "TRUSTED",
            candidateCount = 1,
            failureCount = 0
        ),
        definition = RunDefinitionEntity(
            definitionId = "run-1-definition",
            runId = "run-1",
            universeName = "TEST",
            universeVersion = "v1",
            universeSymbolsCsv = "TEST",
            universeHash = "u",
            configurationVersion = "v1",
            configurationJson = "{\"a\":\"b\"}",
            configurationHash = "c",
            engineBundleVersion = "test",
            createdAtUtc = 2_000L
        ),
        manifests = listOf(
            ReproducibilityManifestEntity(
                manifestId = "run-1-TEST",
                runId = "run-1",
                ticker = "TEST",
                barsHash = "b",
                configurationHash = "c",
                universeHash = "u",
                manifestHash = "m",
                barCount = 60,
                firstBarEpochSeconds = 1L,
                lastBarEpochSeconds = 60L,
                provider = "YAHOO",
                providerHost = "query1.finance.yahoo.com",
                providerStatus = "HIGH",
                fallbackUsed = false,
                cacheHit = false,
                retrievedAtUtc = 1_000L,
                engineVersion = "test"
            )
        ),
        candidates = listOf(candidate()),
        enrichments = emptyList(),
        analyses = emptyList(),
        tradePlans = emptyList(),
        finalDecisions = emptyList()
    )

    private fun candidate(runId: String = "run-1") = CandidateEntity(
        runId = runId,
        ticker = "TEST",
        signal = "WATCHLIST",
        score = 50.0,
        close = 100.0,
        sma20 = 99.0,
        sma50 = 98.0,
        rsi14 = 55.0,
        macd = 1.0,
        macdSignal = 0.5,
        stochastic = 60.0,
        atr14 = 2.0,
        relativeVolume = 1.0,
        entry = null,
        stop = null,
        target = null,
        rr = 2.0,
        reason = "fixture"
    )

    private fun universe(): NormalizedDatasetDecoder.UniverseDataset {
        val snapshot = UniverseSnapshotEntity(
            snapshotId = "u1",
            effectiveDate = "2026-07-20",
            selectionRuleVersion = "v1",
            mode = "US_LISTED_COMMON_EQUITIES",
            symbols = "TEST",
            symbolCount = 1,
            eligibleCount = 1,
            source = "TEST",
            status = "COMPLETE",
            createdAtUtc = 1_000L
        )
        val member = UniverseMemberEntity(
            memberId = "u1-TEST",
            snapshotId = "u1",
            ticker = "TEST",
            sector = null,
            industry = null,
            instrumentType = "EQUITY",
            adrStatus = "NOT_ADR",
            price = 100.0,
            marketCap = 2_000_000_000L,
            averageDollarVolume20 = 50_000_000.0,
            spreadPct = 0.1,
            eligible = true,
            exclusionReasons = "",
            capturedAtUtc = 1_000L
        )
        return NormalizedDatasetDecoder.UniverseDataset(snapshot, listOf(member))
    }
}
