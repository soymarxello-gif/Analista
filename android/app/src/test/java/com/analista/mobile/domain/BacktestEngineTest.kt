package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import com.analista.mobile.data.SignalContractEntity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class BacktestEngineTest {
    @Test
    fun ignoresBarsAtOrBeforeDecisionAndDoesNotTrigger() {
        val contract = contract(decision = 2_000L)
        val bars = listOf(
            bar(1, 100.0, 120.0, 90.0, 110.0),
            bar(2, 100.0, 120.0, 90.0, 110.0),
            bar(3, 100.0, 104.0, 98.0, 102.0)
        )
        val result = BacktestEngine.evaluate(contract, bars)
        assertFalse(result.triggered)
        assertNull(result.entryFill)
        assertNull(result.netPnlUsd)
    }

    @Test
    fun recordsTargetWithCostsPnlAndReturnR() {
        val result = BacktestEngine.evaluate(
            contract(shares = 100),
            listOf(
                bar(2, 104.0, 106.0, 103.0, 105.0),
                bar(3, 106.0, 116.0, 104.0, 115.0)
            )
        )
        assertTrue(result.triggered)
        assertTrue(result.targetHit)
        assertFalse(result.stopHit)
        assertEquals("TARGET", result.firstExitEvent)
        assertEquals("CLOSED_TARGET", result.status)
        assertEquals(115.0, result.exitPrice ?: 0.0, 0.0)
        assertEquals(2.0, result.commissionUsd, 0.0)
        assertNotNull(result.grossPnlUsd)
        assertTrue((result.netPnlUsd ?: 0.0) > 0.0)
        assertTrue((result.returnR ?: 0.0) > 0.0)
        assertTrue((result.entrySlippagePct ?: 0.0) > 0.0)
    }

    @Test
    fun regularStopAppliesAdverseSlippage() {
        val result = BacktestEngine.evaluate(
            contract(shares = 100),
            listOf(
                bar(2, 104.0, 107.0, 103.0, 105.0),
                bar(3, 103.0, 104.0, 94.0, 95.0)
            )
        )
        assertTrue(result.stopHit)
        assertEquals("STOP", result.firstExitEvent)
        assertEquals("CLOSED_STOP", result.status)
        assertTrue((result.exitPrice ?: 100.0) < 95.0)
        assertTrue((result.netPnlUsd ?: 0.0) < 0.0)
        assertTrue((result.returnR ?: 0.0) < -1.0)
    }

    @Test
    fun gapBelowStopFillsAtGapWithAdverseSlippage() {
        val result = BacktestEngine.evaluate(
            contract(shares = 50),
            listOf(
                bar(2, 105.0, 108.0, 102.0, 106.0),
                bar(3, 90.0, 92.0, 88.0, 89.0)
            )
        )
        assertEquals("STOP_GAP", result.exitReason)
        assertTrue((result.exitPrice ?: 100.0) < 90.0)
        assertTrue((result.netPnlUsd ?: 0.0) < 0.0)
    }

    @Test
    fun sameBarStopAndTargetIsAmbiguousWithoutInventedPnl() {
        val result = BacktestEngine.evaluate(
            contract(),
            listOf(bar(2, 104.0, 116.0, 94.0, 108.0))
        )
        assertTrue(result.ambiguousSameBar)
        assertTrue(result.stopHit)
        assertTrue(result.targetHit)
        assertEquals("AMBIGUOUS_SAME_BAR", result.firstExitEvent)
        assertNull(result.exitPrice)
        assertNull(result.netPnlUsd)
    }

    @Test
    fun intradayTriggerAndStopSameBarIsAmbiguousBecauseOrderIsUnknown() {
        val result = BacktestEngine.evaluate(
            contract(),
            listOf(bar(2, 100.0, 106.0, 94.0, 102.0))
        )
        assertTrue(result.ambiguousSameBar)
        assertEquals("AMBIGUOUS_ENTRY_STOP_SAME_BAR", result.firstExitEvent)
        assertNull(result.exitPrice)
    }

    @Test
    fun gapAboveMaximumEntryDoesNotFill() {
        val result = BacktestEngine.evaluate(
            contract(),
            listOf(bar(2, 110.0, 115.0, 108.0, 112.0))
        )
        assertFalse(result.triggered)
    }

    @Test
    fun expirationClosesAtLastCloseAndKeepsMarkoutSeparate() {
        val result = BacktestEngine.evaluate(
            contract(expiration = 2, shares = 10),
            listOf(
                bar(2, 105.0, 108.0, 100.0, 106.0),
                bar(3, 106.0, 109.0, 100.0, 107.0)
            )
        )
        assertEquals("EXPIRATION", result.exitReason)
        assertEquals("EXPIRED", result.status)
        assertNotNull(result.exitPrice)
        assertNotNull(result.tradeReturnPct)
        assertNotNull(result.return1dPct)
    }

    private fun contract(
        decision: Long = 1_000L,
        expiration: Int = 20,
        shares: Int = 1
    ) = SignalContractEntity(
        signalId = "signal", runId = "run", ticker = "TEST", signal = "READY_WAIT_TRIGGER",
        decisionTimestampUtc = decision, referencePrice = 100.0, triggerPrice = 105.0,
        maximumEntry = 108.0, stopPrice = 95.0, targetPrice = 115.0,
        expirationSessions = expiration, engineVersion = "test", createdAtUtc = decision,
        shares = shares
    )

    private fun bar(epoch: Long, open: Double, high: Double, low: Double, close: Double) =
        PriceBar(epochSeconds = epoch, open = open, high = high, low = low, close = close, volume = 1_000_000)
}
