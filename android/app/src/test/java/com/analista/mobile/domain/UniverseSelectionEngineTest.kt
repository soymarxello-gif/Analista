package com.analista.mobile.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UniverseSelectionEngineTest {
    private fun input(
        ticker: String = "TEST",
        type: String? = "EQUITY",
        adrStatus: String? = null,
        price: Double? = 100.0,
        marketCap: Long? = 5_000_000_000L,
        dollarVolume: Double? = 50_000_000.0,
        spread: Double? = 0.20,
        capturedAt: Long = 100L
    ) = UniverseSelectionEngine.Input(
        ticker = ticker,
        sector = "Technology",
        industry = "Software",
        instrumentType = type,
        adrStatus = adrStatus,
        price = price,
        marketCap = marketCap,
        averageDollarVolume20 = dollarVolume,
        spreadPct = spread,
        capturedAtUtc = capturedAt
    )

    @Test
    fun liquidUsListedEquityIsEligible() {
        val result = UniverseSelectionEngine.assess(input())
        assertTrue(result.eligible)
        assertTrue(result.reasons.isEmpty())
    }

    @Test
    fun liquidAdrIsAllowedButIlliquidAdrIsRejected() {
        assertTrue(UniverseSelectionEngine.assess(input(type = "ADR", adrStatus = "LIQUID_ADR")).eligible)
        val illiquid = UniverseSelectionEngine.assess(input(type = "ADR", adrStatus = "ILLIQUID_ADR"))
        assertFalse(illiquid.eligible)
        assertTrue("illiquid_adr" in illiquid.reasons)
    }

    @Test
    fun hardFiltersAndExcludedTypesAccumulate() {
        val result = UniverseSelectionEngine.assess(
            input(type = "ETF", price = 5.0, marketCap = 500_000_000L, dollarVolume = 2_000_000.0, spread = 2.0)
        )
        assertFalse(result.eligible)
        assertEquals(
            setOf("price_below_min", "market_cap_below_min", "dollar_volume_below_min", "spread_unacceptable", "excluded_security_type"),
            result.reasons.toSet()
        )
    }

    @Test
    fun snapshotIsDeterministicRegardlessOfInputOrder() {
        val first = UniverseSelectionEngine.createSnapshot(
            effectiveDate = "2026-07-20",
            inputs = listOf(input("MSFT"), input("AAPL")),
            source = "SHADOW",
            createdAtUtc = 100L
        )
        val second = UniverseSelectionEngine.createSnapshot(
            effectiveDate = "2026-07-20",
            inputs = listOf(input("AAPL"), input("MSFT")),
            source = "SHADOW",
            createdAtUtc = 200L
        )
        assertEquals(first.snapshot.snapshotId, second.snapshot.snapshotId)
        assertEquals("AAPL,MSFT", first.snapshot.symbols)
        assertEquals(listOf("AAPL", "MSFT"), first.members.map { it.ticker })
    }

    @Test(expected = IllegalArgumentException::class)
    fun duplicateSymbolsAreRejected() {
        UniverseSelectionEngine.createSnapshot(
            effectiveDate = "2026-07-20",
            inputs = listOf(input("AAPL"), input("aapl")),
            source = "TEST",
            createdAtUtc = 100L
        )
    }
}
