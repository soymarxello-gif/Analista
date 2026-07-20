package com.analista.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class NormalizedDatasetDecoderTest {
    @Test
    fun barsRoundTripPreservesCanonicalOrderAndValues() {
        val rows = listOf(
            PriceBar(1L, 10.0, 11.0, 9.0, 10.5, 100L),
            PriceBar(2L, 10.5, 12.0, 10.0, 11.5, 200L)
        )
        val decoded = NormalizedDatasetDecoder.bars(NormalizedDatasetCodec.bars("abc", rows.reversed()))
        assertEquals("ABC", decoded.ticker)
        assertEquals(rows, decoded.bars)
    }

    @Test
    fun quoteRoundTripPreservesProviderTimeAndNulls() {
        val quote = MarketQuote(
            bid = 100.0,
            ask = 100.2,
            regularMarketPrice = 100.1,
            preMarketPrice = null,
            marketCap = 2_000_000_000L,
            quoteType = "EQUITY",
            marketState = "PRE",
            capturedAtUtc = 10L,
            providerTimestampUtc = 10L,
            retrievedAtUtc = 20L,
            provider = "ALPACA"
        )
        val decoded = NormalizedDatasetDecoder.quote(NormalizedDatasetCodec.quote("TEST", quote))
        assertEquals("TEST", decoded.ticker)
        assertEquals(100.0, decoded.quote!!.bid!!, 0.0001)
        assertEquals(10L, decoded.quote!!.providerTimestampUtc)
        assertEquals(20L, decoded.quote!!.retrievedAtUtc)
        assertNull(decoded.quote!!.preMarketPrice)
    }

    @Test
    fun macroAndFundamentalsRoundTripRemainRunScoped() {
        val macro = MarketSnapshotEntity("old-SPY", "old", "SPY", "SPY", 600.0, 0.5, 10L)
        val decodedMacro = NormalizedDatasetDecoder.macro(NormalizedDatasetCodec.macro(listOf(macro)), "new")
        assertEquals("new-SPY", decodedMacro.single().snapshotId)
        assertEquals("new", decodedMacro.single().runId)

        val fundamental = fundamental("old", "TEST")
        val decodedFundamental = NormalizedDatasetDecoder.fundamentals(
            NormalizedDatasetCodec.fundamentals(listOf(fundamental)),
            "new"
        ).single()
        assertEquals("new-TEST", decodedFundamental.snapshotId)
        assertEquals(72.0, decodedFundamental.fundamentalScore, 0.0001)
        assertEquals("IMMINENT", decodedFundamental.earningsRiskStatus)
    }

    @Test
    fun optionChainRoundTripPreservesExpiryAndGreeks() {
        val contract = OptionContractSnapshot(
            expiryEpochSeconds = 1000L,
            strike = 105.0,
            type = "CALL",
            bid = 1.0,
            ask = 1.2,
            volume = 10L,
            openInterest = 100L,
            impliedVolatility = 0.3,
            delta = 0.5,
            gamma = 0.02,
            distanceToSpotPct = 5.0,
            lastTradeEpochSeconds = 900L
        )
        val chain = OptionChainSnapshot(
            ticker = "TEST",
            spot = 100.0,
            expiries = listOf(OptionExpirySnapshot(1000L, listOf(contract))),
            availableExpiries = listOf(1000L),
            capturedAtUtc = 10L,
            provider = "YAHOO",
            providerHost = "query2.finance.yahoo.com",
            gammaStatus = "AVAILABLE"
        )
        val decoded = NormalizedDatasetDecoder.options(NormalizedDatasetCodec.options(chain))
        assertEquals(chain.ticker, decoded.ticker)
        assertEquals(1000L, decoded.availableExpiries.single())
        assertEquals(0.02, decoded.expiries.single().contracts.single().gamma!!, 0.0001)
    }

    @Test
    fun universeRoundTripReconstructsCountsAndMembers() {
        val snapshot = UniverseSnapshotEntity(
            snapshotId = "universe-1",
            effectiveDate = "2026-07-20",
            selectionRuleVersion = "rules-1",
            mode = "US_LISTED_COMMON_EQUITIES",
            symbols = "AAA,BBB",
            symbolCount = 2,
            eligibleCount = 1,
            source = "SCAN_RUNTIME",
            status = "PARTIAL",
            createdAtUtc = 10L
        )
        val members = listOf(
            member("universe-1", "BBB", false, 11L),
            member("universe-1", "AAA", true, 10L)
        )
        val decoded = NormalizedDatasetDecoder.universe(NormalizedDatasetCodec.universe(snapshot, members))
        assertEquals(2, decoded.snapshot.symbolCount)
        assertEquals(1, decoded.snapshot.eligibleCount)
        assertEquals(listOf("AAA", "BBB"), decoded.members.map { it.ticker })
        assertEquals(11L, decoded.snapshot.createdAtUtc)
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsNonChronologicalBars() {
        val payload = """{"ticker":"TEST","bars":[{"t":2,"o":10,"h":11,"l":9,"c":10,"v":1},{"t":1,"o":10,"h":11,"l":9,"c":10,"v":1}]}""".toByteArray()
        NormalizedDatasetDecoder.bars(payload)
    }

    private fun fundamental(runId: String, ticker: String) = FundamentalSnapshotEntity(
        snapshotId = "$runId-$ticker",
        runId = runId,
        ticker = ticker,
        revenueYoyPct = 12.0,
        revenueTrend = "IMPROVING",
        epsYoyPct = 15.0,
        epsTrend = "IMPROVING",
        grossMarginPct = 60.0,
        grossMarginDeltaPct = 1.0,
        operatingMarginPct = 25.0,
        operatingMarginDeltaPct = 1.0,
        netMarginPct = 20.0,
        netMarginDeltaPct = 1.0,
        debtToEquity = 30.0,
        debtToEbitda = 1.0,
        interestCoverage = 10.0,
        freeCashFlow = 1_000_000.0,
        priceToSales = 5.0,
        sectorPriceToSalesMedian = 4.0,
        earningsDateUtc = 100L,
        earningsSessions = 2,
        earningsRiskStatus = "IMMINENT",
        dataAgeDays = 1L,
        sector = "TECH",
        coveragePct = 100.0,
        status = "COMPLETE",
        fundamentalScore = 72.0,
        reasons = "fixture",
        engineVersion = "test",
        capturedAtUtc = 10L
    )

    private fun member(snapshotId: String, ticker: String, eligible: Boolean, captured: Long) = UniverseMemberEntity(
        memberId = "$snapshotId-$ticker",
        snapshotId = snapshotId,
        ticker = ticker,
        sector = "TECH",
        industry = "SOFTWARE",
        instrumentType = "EQUITY",
        adrStatus = "NOT_ADR",
        price = 100.0,
        marketCap = 2_000_000_000L,
        averageDollarVolume20 = 50_000_000.0,
        spreadPct = 0.1,
        eligible = eligible,
        exclusionReasons = if (eligible) "" else "fixture",
        capturedAtUtc = captured
    )
}
