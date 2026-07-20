package com.analista.mobile.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RankingPromotionEngineTest {
    @Test
    fun promotesOnlyWhenProposedRankingImprovesOutOfSampleResults() {
        val result = RankingPromotionEngine.evaluate(improvingSample(), walkForwardGatePassed = true)
        assertEquals(150, result.proposed.closed)
        assertTrue(result.expectancyImprovementR!! >= 0.10)
        assertEquals("PROMOTE_PROPOSED_RANKING", result.status)
        assertTrue(result.reasons.isEmpty())
    }

    @Test
    fun equalExpectancyKeepsLegacyOrder() {
        val rows = improvingSample().map { it.copy(tradeReturnR = 0.5, mfePct = 3.0, maePct = -1.0) }
        val result = RankingPromotionEngine.evaluate(rows, walkForwardGatePassed = true)
        assertEquals("KEEP_LEGACY_ORDER", result.status)
        assertTrue("expectancy_improvement_below_threshold" in result.reasons)
    }

    @Test
    fun invalidCandidateInProposedTopKBlocksPromotion() {
        val rows = improvingSample().mapIndexed { index, row ->
            if (index == 0) row.copy(eligibleForContract = false, finalSignal = "WATCHLIST") else row
        }
        val result = RankingPromotionEngine.evaluate(rows, walkForwardGatePassed = true)
        assertEquals("KEEP_LEGACY_ORDER", result.status)
        assertTrue("proposed_ranking_selects_invalid_candidates" in result.reasons)
    }

    @Test
    fun failedWalkForwardGateCannotBeBypassedByStrongRanking() {
        val result = RankingPromotionEngine.evaluate(improvingSample(), walkForwardGatePassed = false)
        assertEquals("KEEP_LEGACY_ORDER", result.status)
        assertTrue("walk_forward_gate_failed" in result.reasons)
    }

    @Test
    fun insufficientRegimeBreadthBlocksPromotion() {
        val rows = improvingSample().map { it.copy(macroRegime = "RISK_ON") }
        val result = RankingPromotionEngine.evaluate(rows, walkForwardGatePassed = true)
        assertFalse(result.status == "PROMOTE_PROPOSED_RANKING")
        assertTrue("insufficient_proposed_regime_breadth" in result.reasons)
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsDuplicateTickerInsideRun() {
        val row = improvingSample().first()
        RankingPromotionEngine.evaluate(listOf(row, row.copy(proposedRank = 2, legacyRank = 2)), true)
    }

    private fun improvingSample(): List<RankingPromotionEngine.Observation> = buildList {
        repeat(30) { runIndex ->
            repeat(10) { tickerIndex ->
                val proposedTop = tickerIndex < 5
                add(
                    RankingPromotionEngine.Observation(
                        runId = "run-$runIndex",
                        ticker = "T$tickerIndex",
                        decisionTimestampUtc = 1_000L + runIndex,
                        legacyRank = 10 - tickerIndex,
                        proposedRank = tickerIndex + 1,
                        finalSignal = "READY_WAIT_TRIGGER",
                        eligibleForContract = true,
                        p0Valid = true,
                        macroRegime = if (runIndex % 2 == 0) "RISK_ON" else "RISK_OFF",
                        tradeReturnR = if (proposedTop) 1.0 else 0.5,
                        mfePct = if (proposedTop) 4.0 else 3.0,
                        maePct = if (proposedTop) -1.0 else -1.1
                    )
                )
            }
        }
    }
}
