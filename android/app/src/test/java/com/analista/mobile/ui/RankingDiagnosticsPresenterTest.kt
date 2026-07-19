package com.analista.mobile.ui

import com.analista.mobile.data.RankingComparisonEntity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RankingDiagnosticsPresenterTest {
    @Test
    fun `missing comparison keeps legacy active`() {
        val model = RankingDiagnosticsPresenter.present(null)
        assertFalse(model.available)
        assertEquals("Ranking legacy activo", model.adoptionLabel)
        assertEquals(listOf("COMPARISON_NOT_AVAILABLE"), model.reasons)
    }

    @Test
    fun `failed thresholds expose reasons and keep legacy active`() {
        val model = RankingDiagnosticsPresenter.present(entity(false, "KEEP_LEGACY_ORDER", "LOW_TOP_K_OVERLAP,LOW_RANK_CORRELATION"))
        assertTrue(model.available)
        assertEquals("Ranking legacy activo", model.adoptionLabel)
        assertEquals(listOf("LOW_TOP_K_OVERLAP", "LOW_RANK_CORRELATION"), model.reasons)
    }

    @Test
    fun `stable shadow comparison does not imply automatic adoption`() {
        val model = RankingDiagnosticsPresenter.present(entity(true, "SHADOW_COMPARISON_STABLE", ""))
        assertTrue(model.available)
        assertTrue(model.adoptionLabel.contains("validación histórica"))
        assertTrue(model.reasons.isEmpty())
    }

    private fun entity(passed: Boolean, status: String, reasons: String) = RankingComparisonEntity(
        comparisonId = "run-ranking",
        runId = "run",
        totalItems = 35,
        comparableItems = 35,
        missingItems = 0,
        topK = 5,
        topKOverlapCount = 4,
        topKOverlapPct = 80.0,
        medianAbsoluteDisplacement = 2.0,
        spearman = 0.88,
        thresholdsPassed = passed,
        status = status,
        reasons = reasons,
        engineVersion = "ranking-comparison-1",
        calculatedAtUtc = 1L
    )
}
