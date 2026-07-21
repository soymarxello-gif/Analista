package com.analista.mobile.data

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.file.Files
import java.time.LocalDate

class RunDatasetCaptureServiceTest {
    @Test
    fun capturesBarsQuotesMacroHistoryInsidersAndUniverseForRuntimeTickers() = runTest {
        val root = Files.createTempDirectory("analista-live-capture").toFile()
        try {
            RunUniverseRegistry.record("run-1", listOf("BBB", "AAA"))
            val service = RunDatasetCaptureService(RunDatasetStore(root))
            val bars = listOf(PriceBar(1L, 10.0, 11.0, 9.0, 10.5, 100L))
            MarketHistoryRegistry.record("SPY", bars)
            InsiderTransactionRegistry.record(
                InsiderTransactionRegistry.Snapshot(
                    ticker = "AAA",
                    transactions = listOf(
                        SecEdgarClient.InsiderTransaction(
                            accessionNumber = "fixture",
                            ticker = "AAA",
                            ownerName = "Director",
                            isDirector = true,
                            isOfficer = false,
                            officerTitle = null,
                            securityTitle = "Common Stock",
                            transactionDate = LocalDate.of(2026, 7, 18),
                            transactionCode = "P",
                            acquiredDisposedCode = "A",
                            shares = 1_000.0,
                            pricePerShare = 10.0,
                            transactionValue = 10_000.0,
                            sharesOwnedFollowing = 2_000.0,
                            directOrIndirect = "D"
                        )
                    ),
                    status = "COMPLETE",
                    capturedAtUtc = 1L
                )
            )
            val quote = MarketQuote(
                bid = 10.4,
                ask = 10.6,
                regularMarketPrice = 10.5,
                preMarketPrice = null,
                marketCap = 2_000_000_000L,
                quoteType = "EQUITY",
                capturedAtUtc = 1L,
                providerTimestampUtc = 1L,
                retrievedAtUtc = 1L,
                provider = "ALPACA"
            )
            val macro = MarketSnapshotEntity(
                snapshotId = "run-1-SPY",
                runId = "run-1",
                symbol = "SPY",
                label = "SPY",
                close = 600.0,
                changePct = 0.5,
                capturedAtUtc = 1L
            )

            val artifacts = service.capture(
                runId = "run-1",
                effectiveDate = "2026-07-20",
                tickers = listOf("BBB", "AAA"),
                barsByTicker = mapOf("AAA" to bars, "BBB" to bars),
                quotesByTicker = mapOf("AAA" to quote, "BBB" to quote),
                macroSnapshots = listOf(macro),
                createdAtUtc = 1L
            )

            assertEquals(8, artifacts.size)
            assertEquals(2, artifacts.count { it.datasetType == "NORMALIZED_BARS" })
            assertEquals(2, artifacts.count { it.datasetType == "EXECUTION_QUOTE" })
            assertEquals(1, artifacts.count { it.datasetType == "MACRO_SNAPSHOT" })
            assertEquals(1, artifacts.count { it.datasetType == "MACRO_HISTORY" })
            assertEquals(1, artifacts.count { it.datasetType == "INSIDER_TRANSACTIONS" })
            assertEquals(1, artifacts.count { it.datasetType == "UNIVERSE_SNAPSHOT" })
            assertTrue(artifacts.all { it.contentHash.length == 64 })
            val store = RunDatasetStore(root)
            assertTrue(artifacts.all { store.verify(it) })
        } finally {
            RunUniverseRegistry.clear()
            FundamentalSnapshotRegistry.clear()
            OptionChainRegistry.clear()
            InsiderTransactionRegistry.clear()
            MarketHistoryRegistry.clear()
            root.deleteRecursively()
        }
    }
}
