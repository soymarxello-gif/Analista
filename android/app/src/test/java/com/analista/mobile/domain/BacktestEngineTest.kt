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
    }

    @Test
    fun gapAboveMaximumEntryDoesNotFill() {
        val result = BacktestEngine.evaluate(
            contract(),
            listOf(bar(2, 110.0, 115.0, 108.0, 112.0))
        )
        assertFalse(result.triggered)
    }

    private fun contract(decision: Long = 1_000L) = SignalContractEntity(
        signalId = "signal", runId = "run", ticker = "TEST", signal = "READY_WAIT_TRIGGER",
        decisionTimestampUtc = decision, referencePrice = 100.0, triggerPrice = 105.0,
        maximumEntry = 108.0, stopPrice = 95.0, targetPrice = 115.0,
        expirationSessions = 20, engineVersion = "test", createdAtUtc = decision
    )

    private fun bar(epoch: Long, open: Double, high: Double, low: Double, close: Double) =
        PriceBar(epochSeconds = epoch, open = open, high = high, low = low, close = close, volume = 1_000_000)
}
