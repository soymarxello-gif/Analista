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

        val institutionalConflict = if (
            overlay.optionsCoverage == "COMPLETE" &&
            overlay.optionsBias == "BEARISH_WITH_DATA" &&
            overlay.institutionalScore <= 40.0
        ) "HIGH" else "NONE"
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
                institutionalConflict = institutionalConflict,
                riskPlanValid = aggressiveStop.valid,
                liveTriggerConfirmed = candidate.liveTriggerConfirmed,
                actionability = candidate.actionabilityAtExecution,
                executionQuoteQuality = candidate.executionQuoteQuality,
                executionFreshness = candidate.quoteFreshnessStatus,
                dataQualityAllowsExecution = dataQualityAllowsExecution,
                failedBreakout = candidate.failedBreakout,
                hardVetoReasons = candidate.allVetoReasons,
                penaltyReasons = (candidate.penaltyReasons + aggressiveStop.reasons).distinct()
            )
        )

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
            decisionVersion = "${evaluated.decisionVersion}+${AggressiveStopPolicy.VERSION}+${MacroRegimeEngine.VERSION}",
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
                engineVersion = "$engineVersion+${FinalDecisionEngine.VERSION}+${QuoteFreshnessEngine.VERSION}+${AggressiveStopPolicy.VERSION}+${MacroRegimeEngine.VERSION}",
                createdAtUtc = calculatedAtUtc
            )
        } else null

        return Result(entity, contract)
    }
}
