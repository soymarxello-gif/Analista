package com.analista.mobile.domain

import com.analista.mobile.data.CandidateAnalysisEntity
import com.analista.mobile.data.CandidateTradePlanEntity
import com.analista.mobile.data.FinalDecisionEntity
import com.analista.mobile.data.ScanCandidate
import com.analista.mobile.data.SignalContractEntity

object FinalDecisionPersistenceFactory {
    data class Result(
        val decision: FinalDecisionEntity,
        val contract: SignalContractEntity?
    )

    fun create(
        runId: String,
        candidate: ScanCandidate,
        analysis: CandidateAnalysisEntity,
        overlay: DecisionOverlayEngine.OverlayResult,
        plan: CandidateTradePlanEntity,
        dataQualityAllowsExecution: Boolean,
        macroConfidence: String,
        decisionTimestampUtc: Long,
        calculatedAtUtc: Long,
        engineVersion: String
    ): Result {
        require(runId.isNotBlank())
        require(candidate.ticker == analysis.ticker && candidate.ticker == plan.ticker)
        require(candidate.plannedTrigger != null)
        require(candidate.maximumEntry != null)

        val aggressiveStop = AggressiveStopPolicy.evaluate(
            AggressiveStopPolicy.Input(
                baseRiskPlanValid = plan.riskPlanValid,
                stopAtrMultiple = plan.stopAtrMultiple,
                riskReward = plan.structuralRr,
                structureScore = plan.structureScore,
                setupQualityScore = analysis.setupQualityScore,
                liveTriggerConfirmed = candidate.liveTriggerConfirmed,
                executionQuoteQuality = candidate.executionQuoteQuality
            )
        )
        val resolvedMacroConfidence = overlay.macroConfidence
            .takeUnless { it == "UNKNOWN" }
            ?: macroConfidence
        val evaluated = FinalDecisionEngine.decide(
            FinalDecisionEngine.Input(
                preliminarySignal = candidate.signal,
                finalTradeScore = analysis.finalTradeScore,
                setupType = candidate.setupType,
                setupValid = candidate.setupType != "NO_VALID_SETUP",
                macroRegime = overlay.macroRegime,
                macroConfidence = resolvedMacroConfidence,
                fundamentalCoverage = overlay.fundamentalCoverage,
                institutionalCoverage = overlay.optionsCoverage,
                institutionalConflict = overlay.institutionalConflict,
                riskPlanValid = aggressiveStop.valid,
                liveTriggerConfirmed = candidate.liveTriggerConfirmed,
                actionability = candidate.actionabilityAtExecution,
                executionQuoteQuality = candidate.executionQuoteQuality,
                executionFreshness = candidate.quoteFreshnessStatus,
                executionSessionOpen = candidate.executionSessionOpen,
                eligibilityVerified = candidate.eligibilityVerified,
                dataQualityAllowsExecution = dataQualityAllowsExecution,
                failedBreakout = candidate.failedBreakout,
                hardVetoReasons = candidate.allVetoReasons,
                penaltyReasons = (candidate.penaltyReasons + aggressiveStop.reasons).distinct()
            )
        )

        val decisionBundle = listOf(
            evaluated.decisionVersion,
            AggressiveStopPolicy.VERSION,
            MacroRegimeEngine.VERSION,
            FundamentalAssessmentEngine.VERSION,
            OptionMetricsEngine.VERSION,
            InstitutionalContrarianEngine.VERSION
        ).joinToString("+")
        val entity = FinalDecisionEntity(
            decisionId = "$runId-${candidate.ticker}",
            runId = runId,
            ticker = candidate.ticker,
            preliminarySignal = evaluated.preliminarySignal,
            finalSignal = evaluated.finalSignal,
            finalTradeScore = evaluated.finalTradeScore,
            eligibleForContract = evaluated.eligibleForContract,
            confidence = evaluated.confidence,
            vetoReasons = evaluated.vetoReasons.joinToString(","),
            penaltyReasons = evaluated.penaltyReasons.joinToString(","),
            macroRegime = overlay.macroRegime,
            fundamentalCoverage = overlay.fundamentalCoverage,
            institutionalCoverage = overlay.optionsCoverage,
            executionFreshness = candidate.quoteFreshnessStatus,
            decisionVersion = decisionBundle,
            calculatedAtUtc = calculatedAtUtc
        )

        val contract = if (evaluated.eligibleForContract) {
            SignalContractEntity(
                signalId = "$runId-${candidate.ticker}",
                runId = runId,
                ticker = candidate.ticker,
                signal = evaluated.finalSignal,
                decisionTimestampUtc = decisionTimestampUtc,
                referencePrice = candidate.referenceClose ?: candidate.close,
                triggerPrice = candidate.plannedTrigger,
                maximumEntry = candidate.maximumEntry,
                stopPrice = plan.structuralStop,
                targetPrice = plan.structuralTarget,
                expirationSessions = 20,
                engineVersion = "$engineVersion+$decisionBundle+${QuoteFreshnessEngine.VERSION}+${BacktestEngine.VERSION}",
                createdAtUtc = calculatedAtUtc,
                shares = plan.shares,
                positionValue = plan.positionValue,
                riskBudget = plan.riskBudget
            )
        } else null

        return Result(entity, contract)
    }
}
