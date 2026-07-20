package com.analista.mobile.ui

import com.analista.mobile.data.ReplayResultEntity
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ReplayDiagnosticsPresenterTest {
    @Test
    fun completeFullMatchIsTrustworthy() {
        val model = ReplayDiagnosticsPresenter.present(entity(status = "COMPLETE", matched = 35))
        assertTrue(model.trustworthy)
        assertTrue(model.hasData)
    }

    @Test
    fun mismatchCanNeverBePresentedAsTrustworthy() {
        val model = ReplayDiagnosticsPresenter.present(
            entity(status = "MISMATCH", matched = 34, mismatches = 1, reasons = "replay_mismatches_detected")
        )
        assertFalse(model.trustworthy)
        assertTrue("replay_mismatches_detected" in model.reasons)
    }

    @Test
    fun absentReplayIsExplicitNoData() {
        val model = ReplayDiagnosticsPresenter.present(null)
        assertFalse(model.trustworthy)
        assertFalse(model.hasData)
        assertTrue("replay_not_executed" in model.reasons)
    }

    private fun entity(
        status: String,
        matched: Int,
        mismatches: Int = 0,
        reasons: String = ""
    ) = ReplayResultEntity(
        replayId = "run-replay",
        runId = "run",
        status = status,
        expectedTickers = 35,
        replayedTickers = 35,
        fullyMatchedTickers = matched,
        mismatchedTickers = mismatches,
        missingDatasetCount = 0,
        reasons = reasons,
        tickerDetails = "",
        engineVersion = "test",
        evaluatedAtUtc = 1L
    )
}
