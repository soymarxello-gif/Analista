package com.analista.mobile.domain

import com.analista.mobile.data.ScanCandidate
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class InsiderScanSelectionPolicyTest {
    @Test
    fun selectsHighestPriorityNonVetoCandidatesOnly() {
        val selected = InsiderScanSelectionPolicy.select(
            listOf(
                candidate("LOW", "WATCHLIST", 55.0),
                candidate("BEST", "TRIGGER_CONFIRMED", 90.0),
                candidate("VETOED", "VETO", 100.0),
                candidate("AVOIDED", "AVOID", 95.0),
                candidate("READY", "READY_WAIT_TRIGGER", 80.0),
                candidate("NOSETUP", "WATCHLIST", 85.0, setup = "NO_VALID_SETUP")
            ),
            maxTickers = 2
        )

        assertEquals(listOf("BEST", "READY"), selected)
        assertFalse("VETOED" in selected)
        assertFalse("AVOIDED" in selected)
    }

    @Test
    fun normalizesAndDeduplicatesTickers() {
        val selected = InsiderScanSelectionPolicy.select(
            listOf(
                candidate("brk.b", "WATCHLIST", 70.0),
                candidate("BRK-B", "READY_WAIT_TRIGGER", 65.0)
            )
        )

        assertEquals(listOf("BRK-B"), selected)
    }

    private fun candidate(
        ticker: String,
        signal: String,
        score: Double,
        setup: String = "BREAKOUT"
    ) = ScanCandidate(
        ticker = ticker,
        signal = signal,
        score = score,
        close = 100.0,
        sma20 = 95.0,
        sma50 = 90.0,
        rsi14 = 55.0,
        macd = 1.0,
        macdSignal = 0.5,
        stochastic = 60.0,
        atr14 = 2.0,
        relativeVolume = 1.2,
        entry = null,
        stop = null,
        target = null,
        rr = 2.0,
        reason = "fixture",
        setupType = setup
    )
}
