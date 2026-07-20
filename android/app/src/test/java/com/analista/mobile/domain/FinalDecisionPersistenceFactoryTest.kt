package com.analista.mobile.domain

import com.analista.mobile.data.CandidateAnalysisEntity
import com.analista.mobile.data.CandidateTradePlanEntity
import com.analista.mobile.data.ScanCandidate
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class FinalDecisionPersistenceFactoryTest {
    private fun candidate(
        signal: String = "READY_WAIT_TRIGGER",
        liveTrigger: Boolean = false,
        quoteQuality: String = "HIGH",
        freshness: String = "FRESH",
        failedBreakout: Boolean = false,
        actionability: String = "WAIT_TRIGGER"
    ) = ScanCandidate(
        ticker = "TEST", signal = signal, score = 80.0, close = 100.0,
        sma20 = 98.0, sma50 = 95.0, rsi14 = 60.0, macd = 1.0, macdSignal = 0.5,
        stochastic = 60.0, atr14 = 2.0, relativeVolume = 1.5,
        entry = null, stop = null, target = null, rr = 2.5, reason = "fixture",
        quoteStatus = "VALID", executionQuoteQuality = quoteQuality,
        triggerConfirmed = liveTrigger, setupType = "BREAKOUT",
        plannedTrigger = 101.0, maximumEntry = 102.0,
        actionabilityAtExecution = actionability,
        priorSessionBreakout = true, liveTriggerConfirmed = liveTrigger,
        breakoutHolding = liveTrigger, failedBreakout = failedBreakout,
        executionPrice = if (liveTrigger) 101.5 else 100.5,
        quoteFreshnessStatus = freshness
    )

    private fun analysis(score: Double = 80.0) = CandidateAnalysisEntity(
        analysisId = "run-TEST", runId = "run", ticker = "TEST",
        rsi6 = 62.0, rsi14Canonical = 60.0, rsi6GtRsi14 = true,
        ema20 = 98.0, ema50 = 95.0, ema200 = 80.0,
        priceVsEma20Pct = 2.0, priceVsEma50Pct = 5.0, priceVsEma200Pct = 25.0,
        weeklyTrend = "UP", assetQualityScore = 80.0, setupQualityScore = 80.0,
        contextScore = 60.0, institutionalScore = 55.0, riskScore = 80.0,
        finalTradeScore = score, stopAtrMultiple = 1.5, stopAtrStatus = "PREFERRED",
        scoreBreakdown = "fixture", engineVersion = "fixture", calculatedAtUtc = 1L
    )

    private fun plan(valid: Boolean = true) = CandidateTradePlanEntity(
        planId = "run-TEST", runId = "run", ticker = "TEST",
        priorResistance = 100.0, nextResistance = 110.0, swingLow = 96.0,
        closeLocationValue = 0.8, baseRangeAtr = 3.0, volatilityCompression = 0.7,
        resistanceTouches = 3, structureScore = 85.0,
        rs20VsSpy = 4.0, rs60VsSpy = 8.0, relativeStrengthScore = 70.0,
        relativeStrengthStatus = "STRONG", plannedEntry = 101.0,
        structuralStop = 97.0, structuralTarget = 109.0, stopType = "STRUCTURE",
        stopAtrMultiple = 2.0, structuralRr = 2.0, riskPct = 3.96, rewardPct = 7.92,
        shares = 50, positionValue = 5_050.0, riskBudget = 250.0,
        riskPlanValid = valid, legacyRank = 1, tradeRank = 1, rankDelta = 0,
        auditedTradeScore = 82.0, reasons = "fixture", engineVersion = "fixture",
        calculatedAtUtc = 1L
    )

    private fun overlay(
        optionsBias: String = "NEUTRAL_WITH_DATA",
        optionsCoverage: String = "COMPLETE",
        institutionalScore: Double = 50.0
    ) = DecisionOverlayEngine.OverlayResult(
        contextScore = 60.0, fundamentalScore = 60.0,
        institutionalScore = institutionalScore, finalTradeScore = 80.0,
        macroRegime = "RISK_ON", optionsBias = optionsBias,
        fundamentalCoverage = "COMPLETE", optionsCoverage = optionsCoverage,
        confidencePenalty = 0.0, breakdown = "fixture"
    )

    private fun create(
        candidate: ScanCandidate = candidate(),
        analysis: CandidateAnalysisEntity = analysis(),
        plan: CandidateTradePlanEntity = plan(),
        overlay: DecisionOverlayEngine.OverlayResult = overlay(),
        dataAllowed: Boolean = true
    ) = FinalDecisionPersistenceFactory.create(
        runId = "run", candidate = candidate, analysis = analysis, overlay = overlay,
        plan = plan, dataQualityAllowsExecution = dataAllowed, macroConfidence = "HIGH",
        decisionTimestampUtc = 100L, calculatedAtUtc = 200L, engineVersion = "bundle"
    )

    @Test
    fun validReadyDecisionCreatesImmutableContract() {
        val result = create()
        assertEquals("READY_WAIT_TRIGGER", result.decision.finalSignal)
        assertTrue(result.decision.eligibleForContract)
        assertEquals("FRESH", result.decision.executionFreshness)
        assertEquals("READY_WAIT_TRIGGER", result.contract?.signal)
        assertEquals(101.0, result.contract?.triggerPrice ?: 0.0, 0.0)
    }

    @Test
    fun staleDecisionIsPersistedButNeverCreatesContract() {
        val result = create(candidate = candidate(freshness = "STALE"))
        assertEquals("STALE", result.decision.executionFreshness)
        assertEquals("WATCHLIST", result.decision.finalSignal)
        assertNull(result.contract)
    }

    @Test
    fun bearishInstitutionalConflictBlocksContract() {
        val result = create(overlay = overlay("BEARISH_WITH_DATA", "COMPLETE", 38.0))
        assertEquals("WATCHLIST", result.decision.finalSignal)
        assertNull(result.contract)
        assertTrue("institutional_conflict_high" in result.decision.penaltyReasons)
    }

    @Test
    fun invalidRiskPlanBlocksContractWithoutImpossibleScoreCheck() {
        val result = create(analysis = analysis(100.0), plan = plan(false))
        assertEquals("AVOID", result.decision.finalSignal)
        assertNull(result.contract)
    }

    @Test
    fun liveTriggerCanCreateConfirmedContractOnlyWhenFreshAndActionable() {
        val result = create(candidate = candidate(
            signal = "TRIGGER_CONFIRMED", liveTrigger = true,
            actionability = "ACTIONABLE_REVIEW"
        ))
        assertEquals("TRIGGER_CONFIRMED", result.decision.finalSignal)
        assertEquals("TRIGGER_CONFIRMED", result.contract?.signal)
    }
}
