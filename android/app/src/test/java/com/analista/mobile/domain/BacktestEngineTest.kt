package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import com.analista.mobile.data.SignalContractEntity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
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
    }

    @Test
    fun recordsTargetAsFirstExitEvent() {
        val result = BacktestEngine.evaluate(
            contract(),
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
        assertTrue(result.exitFill != null)
    }

    @Test
    fun recordsStopAsFirstExitEvent() {
        val result = BacktestEngine.evaluate(
            contract(),
            listOf(
                bar(2, 104.0, 107.0, 103.0, 105.0),
                bar(3, 103.0, 104.0, 94.0, 95.0)
            )
        )
        assertTrue(result.stopHit)
        assertEquals("STOP", result.firstExitEvent)
        assertEquals("CLOSED_STOP", result.status)
    }

    @Test
    fun sameBarStopAndTargetIsAmbiguous() {
        val result = BacktestEngine.evaluate(
            contract(),
            listOf(bar(2, 104.0, 116.0, 94.0, 108.0))
        )
        assertTrue(result.ambiguousSameBar)
        assertTrue(result.stopHit)
        assertTrue(result.targetHit)
        assertEquals("AMBIGUOUS_SAME_BAR", result.firstExitEvent)
        assertNull(result.exitFill)
        assertNull(result.tradeReturnR)
    }

    @Test
    fun intradayActivationAndStopInSameBarIsAmbiguous() {
        val result = BacktestEngine.evaluate(
            contract(),
            listOf(bar(2, 100.0, 106.0, 94.0, 102.0))
        )
        assertTrue(result.triggered)
        assertTrue(result.ambiguousSameBar)
        assertEquals("AMBIGUOUS_ENTRY_STOP_SAME_BAR", result.exitReason)
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
    fun gapBelowStopUsesOpeningFill() {
        val result = BacktestEngine.evaluate(
            contract(),
            listOf(
                bar(2, 106.0, 107.0, 100.0, 105.0),
                bar(3, 90.0, 92.0, 88.0, 89.0)
            )
        )
        assertEquals("GAP_STOP", result.exitReason)
        assertEquals("CLOSED_STOP", result.status)
        assertTrue(result.exitFill!! < 90.0)
    }

    @Test
    fun calculatesRealizedRAndMonetaryPnlWithCosts() {
        val result = BacktestEngine.evaluate(
            contract(shares = 100),
            listOf(
                bar(2, 105.0, 107.0, 100.0, 106.0),
                bar(3, 110.0, 116.0, 109.0, 115.0)
            ),
            costs = BacktestEngine.CostModel(
                entrySlippageBps = 0.0,
                exitSlippageBps = 0.0,
                commissionPerShare = 0.01,
                version = "fixture-costs"
            )
        )
        assertEquals(1.0, result.tradeReturnR!!, 0.0001)
        assertEquals(1000.0, result.grossPnl!!, 0.0001)
        assertEquals(2.0, result.totalCosts!!, 0.0001)
        assertEquals(998.0, result.netPnl!!, 0.0001)
        assertEquals("fixture-costs", result.costModelVersion)
    }

    @Test
    fun expiresAtLastCloseAndKeepsMarkoutsSeparate() {
        val result = BacktestEngine.evaluate(
            contract(expiration = 2),
            listOf(
                bar(2, 105.0, 108.0, 100.0, 106.0),
                bar(3, 106.0, 110.0, 101.0, 109.0)
            ),
            costs = BacktestEngine.CostModel(entrySlippageBps = 0.0, exitSlippageBps = 0.0)
        )
        assertEquals("EXPIRED", result.exitReason)
        assertEquals("CLOSED_EXPIRED", result.status)
        assertEquals(109.0, result.exitFill!!, 0.0001)
        assertTrue(result.return1dPct != null)
    }

    private fun contract(
        decision: Long = 1_000L,
        expiration: Int = 20,
        shares: Int = 0
    ) = SignalContractEntity(
        signalId = "signal", runId = "run", ticker = "TEST", signal = "READY_WAIT_TRIGGER",
        decisionTimestampUtc = decision, referencePrice = 100.0, triggerPrice = 105.0,
        maximumEntry = 108.0, stopPrice = 95.0, targetPrice = 115.0,
        expirationSessions = expiration, engineVersion = "test", createdAtUtc = decision,
        shares = shares, positionValue = if (shares > 0) shares * 105.0 else 0.0,
        riskBudget = if (shares > 0) shares * 10.0 else 0.0
    )

    private fun bar(epoch: Long, open: Double, high: Double, low: Double, close: Double) =
        PriceBar(epochSeconds = epoch, open = open, high = high, low = low, close = close, volume = 1_000_000)
}
