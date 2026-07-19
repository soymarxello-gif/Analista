package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TradePlanGenerationEngineTest {
    @Test
    fun `valid setup receives risk plan and audited ranking`() {
        val benchmark = bars(100.0, 0.20)
        val strong = bars(100.0, 0.45)
        val weak = bars(100.0, 0.10)
        val rows = TradePlanGenerationEngine.generate(
            listOf(
                input("STRONG", "READY_WAIT_TRIGGER", "BREAKOUT", 72.0, 78.0, strong, benchmark),
                input("WEAK", "WATCHLIST", "PULLBACK", 80.0, 62.0, weak, benchmark)
            )
        )
        val strongPlan = rows.first { it.ticker == "STRONG" }
        assertTrue(strongPlan.riskPlan.shares >= 0)
        assertTrue(strongPlan.auditedTradeScore >= 0.0)
        assertEquals(1, strongPlan.tradeRank)
        assertTrue(strongPlan.relativeStrength != null)
    }

    @Test
    fun `veto remains ineligible even with high legacy score`() {
        val benchmark = bars(100.0, 0.20)
        val rows = TradePlanGenerationEngine.generate(
            listOf(
                input("VALID", "READY_WAIT_TRIGGER", "BREAKOUT", 60.0, 70.0, bars(100.0, 0.30), benchmark),
                input("VETOED", "VETO", "BREAKOUT", 99.0, 95.0, bars(100.0, 0.50), benchmark)
            )
        )
        val veto = rows.first { it.ticker == "VETOED" }
        assertFalse(veto.eligibleForOperationalRanking)
        assertTrue(veto.auditedTradeScore <= 49.0)
        assertTrue(veto.reasons.contains("operational_ranking_ineligible"))
    }

    @Test
    fun `missing benchmark is explicit and neutral`() {
        val row = TradePlanGenerationEngine.generate(
            listOf(input("A", "WATCHLIST", "PULLBACK", 50.0, 55.0, bars(100.0, 0.20), null))
        ).single()
        assertEquals(null, row.relativeStrength)
        assertTrue(row.reasons.contains("relative_strength_unavailable"))
    }

    private fun input(
        ticker: String,
        signal: String,
        setupType: String,
        legacyScore: Double,
        finalTradeScore: Double,
        bars: List<PriceBar>,
        benchmark: List<PriceBar>?
    ) = TradePlanGenerationEngine.Input(
        ticker = ticker,
        signal = signal,
        setupType = setupType,
        legacyScore = legacyScore,
        finalTradeScore = finalTradeScore,
        bars = bars,
        benchmarkBars = benchmark,
        entry = bars.last().close,
        atr = 2.0,
        sma20 = bars.takeLast(20).map { it.close }.average()
    )

    private fun bars(start: Double, step: Double): List<PriceBar> = (0 until 80).map { index ->
        val close = start + index * step
        PriceBar(
            epochSeconds = 1_700_000_000L + index * 86_400L,
            open = close - 0.4,
            high = close + 0.8,
            low = close - 0.8,
            close = close,
            volume = 2_000_000L
        )
    }
}
