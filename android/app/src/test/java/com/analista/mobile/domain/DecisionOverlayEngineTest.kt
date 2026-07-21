package com.analista.mobile.domain

import com.analista.mobile.data.CandidateEnrichmentEntity
import com.analista.mobile.data.CanonicalAnalysis
import com.analista.mobile.data.FundamentalMetrics
import com.analista.mobile.data.FundamentalSnapshotRegistry
import com.analista.mobile.data.InsiderTransactionRegistry
import com.analista.mobile.data.MarketHistoryRegistry
import com.analista.mobile.data.MarketSnapshotEntity
import com.analista.mobile.data.OfficialContextRegistry
import com.analista.mobile.data.OptionChainRegistry
import com.analista.mobile.data.OptionChainSnapshot
import com.analista.mobile.data.OptionContractSnapshot
import com.analista.mobile.data.OptionExpirySnapshot
import com.analista.mobile.data.ScanCandidate
import com.analista.mobile.data.SecEdgarClient
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.time.LocalDate
import java.time.ZoneOffset

class DecisionOverlayEngineTest {
    @Before
    fun clearRegistries() {
        OptionChainRegistry.clear()
        FundamentalSnapshotRegistry.clear()
        MarketHistoryRegistry.clear()
        OfficialContextRegistry.clear()
        InsiderTransactionRegistry.clear()
    }

    @Test
    fun missingOptionsRemainUnknownAndReduceConfidence() {
        val result = DecisionOverlayEngine.apply(candidate(), base(), macro(), null)
        assertEquals("UNKNOWN_OPTIONS_FLOW", result.optionsBias)
        assertEquals("UNKNOWN", result.optionsCoverage)
        assertTrue(result.confidencePenalty > 0.0)
    }

    @Test
    fun crowdedBullishOptionsReceiveContrarianPenalty() {
        val crowded = enrichment(putCall = 0.20)
        val neutral = enrichment(putCall = 0.90)
        val crowdedResult = DecisionOverlayEngine.apply(candidate(), base(), macro(), crowded)
        val neutralResult = DecisionOverlayEngine.apply(candidate(), base(), macro(), neutral)
        assertEquals("CROWDED_BULLISH", crowdedResult.optionsBias)
        assertTrue(crowdedResult.finalTradeScore < neutralResult.finalTradeScore)
    }

    @Test
    fun normalizedStrikeDataOverridesLegacyAggregateAndCanFlagConflict() {
        OptionChainRegistry.record(chain(
            callOi = 300L,
            putOi = 1_500L,
            callVolume = 50L,
            putVolume = 400L
        ))
        val result = DecisionOverlayEngine.apply(candidate(), base(final = 85.0), macro(), enrichment(putCall = 0.40))
        assertEquals("CROWDED_BEARISH", result.optionsBias)
        assertEquals("HIGH", result.institutionalConflict)
        assertTrue(result.finalTradeScore <= 59.0)
        assertTrue(result.institutionalReasons.contains("institutional_conflict_high"))
    }

    @Test
    fun registeredOpenMarketPurchaseRaisesInstitutionalEvidence() {
        val baseline = DecisionOverlayEngine.apply(candidate(), base(), macro(), enrichment(putCall = 0.90))
        val captured = LocalDate.of(2026, 7, 21).atStartOfDay().toInstant(ZoneOffset.UTC).toEpochMilli()
        InsiderTransactionRegistry.record(
            InsiderTransactionRegistry.Snapshot(
                ticker = "TEST",
                transactions = listOf(
                    insider("Director A", "P", "A", 5_000.0, 30.0, LocalDate.of(2026, 7, 15)),
                    insider("Director B", "P", "A", 4_000.0, 28.0, LocalDate.of(2026, 7, 16))
                ),
                status = "COMPLETE",
                capturedAtUtc = captured
            )
        )

        val withInsiders = DecisionOverlayEngine.apply(candidate(), base(), macro(), enrichment(putCall = 0.90))

        assertTrue(withInsiders.institutionalScore > baseline.institutionalScore)
        assertTrue("sec_open_market_purchases_present" in withInsiders.institutionalReasons)
        assertTrue("sec_multiple_distinct_buyers" in withInsiders.institutionalReasons)
    }

    @Test
    fun pureResolvedPathMatchesLegacyRuntimePath() {
        val enrichment = enrichment(putCall = 0.90)
        val runtime = DecisionOverlayEngine.apply(candidate(), base(), macro(), enrichment)
        val replay = DecisionOverlayEngine.applyResolved(
            candidate = candidate(),
            base = base(),
            macro = macro(),
            inputs = DecisionOverlayEngine.ResolvedInputs(
                macroHistories = emptyMap(),
                fundamentalMetrics = fundamental(enrichment),
                fundamentalAvailable = true,
                fundamentalCapturedAtUtc = enrichment.capturedAtUtc,
                optionChain = null,
                legacyEnrichment = enrichment
            )
        )
        assertEquals(runtime, replay)
    }

    @Test
    fun vetoCanNeverExceedFortyNine() {
        val result = DecisionOverlayEngine.apply(candidate(signal = "VETO"), base(final = 95.0), macro(), enrichment(0.80))
        assertTrue(result.finalTradeScore <= 49.0)
    }

    private fun chain(callOi: Long, putOi: Long, callVolume: Long, putVolume: Long) = OptionChainSnapshot(
        ticker = "TEST",
        spot = 100.0,
        expiries = listOf(
            OptionExpirySnapshot(
                1_800_000_000L,
                listOf(
                    contract("CALL", 105.0, callOi, callVolume, 0.25, 5.0),
                    contract("PUT", 95.0, putOi, putVolume, 0.40, -5.0)
                )
            )
        ),
        availableExpiries = listOf(1_800_000_000L),
        capturedAtUtc = 1L,
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

    private fun insider(
        owner: String,
        code: String,
        acquiredDisposed: String,
        shares: Double,
        price: Double,
        date: LocalDate
    ) = SecEdgarClient.InsiderTransaction(
        accessionNumber = "fixture-$owner",
        ticker = "TEST",
        ownerName = owner,
        isDirector = true,
        isOfficer = false,
        officerTitle = null,
        securityTitle = "Common Stock",
        transactionDate = date,
        transactionCode = code,
        acquiredDisposedCode = acquiredDisposed,
        shares = shares,
        pricePerShare = price,
        transactionValue = shares * price,
        sharesOwnedFollowing = 20_000.0,
        directOrIndirect = "D"
    )

    private fun macro() = listOf(
        snapshot("SPY", 1.0, 600.0), snapshot("QQQ", 1.1, 550.0), snapshot("IWM", 0.8, 240.0),
        snapshot("VIX", -2.0, 17.0), snapshot("US10Y", 0.2, 4.2), snapshot("DXY", -0.1, 99.0)
    )

    private fun snapshot(label: String, change: Double, close: Double) = MarketSnapshotEntity(
        snapshotId = label, runId = "run", symbol = label, label = label,
        close = close, changePct = change, capturedAtUtc = 1L
    )

    private fun enrichment(putCall: Double) = CandidateEnrichmentEntity(
        enrichmentId = "e", runId = "run", ticker = "TEST", marketCap = 5_000_000_000,
        trailingPe = 20.0, priceToSales = 3.0, epsTrailing = 5.0, revenueGrowthPct = 15.0,
        grossMarginPct = 45.0, operatingMarginPct = 18.0, profitMarginPct = 12.0,
        debtToEquity = 60.0, optionsPutCallOi = putCall, optionsNearCallOi = 1000,
        optionsNearPutOi = 900, optionsExpiry = 1_800_000_000,
        fundamentalsStatus = "AVAILABLE_COMPLETE", optionsStatus = "AVAILABLE_COMPLETE", capturedAtUtc = 1L
    )

    private fun fundamental(e: CandidateEnrichmentEntity) = FundamentalMetrics(
        marketCap = e.marketCap,
        trailingPe = e.trailingPe,
        priceToSales = e.priceToSales,
        epsTrailing = e.epsTrailing,
        revenueGrowthPct = e.revenueGrowthPct,
        grossMarginPct = e.grossMarginPct,
        operatingMarginPct = e.operatingMarginPct,
        profitMarginPct = e.profitMarginPct,
        debtToEquity = e.debtToEquity
    )

    private fun base(final: Double = 70.0) = CanonicalAnalysis(
        rsi6 = 60.0, rsi14 = 55.0, ema20 = 100.0, ema50 = 95.0, ema200 = 80.0,
        macd = 2.0, macdSignal = 1.0, atr14 = 3.0, weeklyTrend = "UP",
        assetQualityScore = 80.0, setupQualityScore = 75.0, contextScore = 50.0,
        institutionalScore = 50.0, riskScore = 80.0, finalTradeScore = final,
        stopAtrMultiple = 1.5, stopAtrStatus = "PREFERRED", scoreBreakdown = "base"
    )

    private fun candidate(signal: String = "WATCHLIST") = ScanCandidate(
        ticker = "TEST", signal = signal, score = 70.0, close = 100.0, sma20 = 95.0,
        sma50 = 90.0, rsi14 = 55.0, macd = 2.0, macdSignal = 1.0,
        stochastic = 60.0, atr14 = 3.0, relativeVolume = 1.3,
        entry = null, stop = null, target = null, rr = 2.5, reason = "test",
        quoteStatus = "VALID", executionQuoteQuality = "HIGH", triggerConfirmed = false,
        setupType = "BREAKOUT_OR_PULLBACK"
    )
}
