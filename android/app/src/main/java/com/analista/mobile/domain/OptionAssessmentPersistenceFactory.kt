package com.analista.mobile.domain

import com.analista.mobile.data.OptionAssessmentEntity
import com.analista.mobile.data.OptionChainSnapshot

object OptionAssessmentPersistenceFactory {
    const val VERSION = "option-assessment-persistence-1"

    fun create(
        runId: String,
        ticker: String,
        chain: OptionChainSnapshot,
        technicalScore: Double = 50.0,
        capturedAtUtc: Long = chain.capturedAtUtc
    ): OptionAssessmentEntity {
        require(runId.isNotBlank())
        require(ticker.isNotBlank())
        val options = OptionMetricsEngine.assess(chain)
        val institutional = InstitutionalContrarianEngine.assess(
            InstitutionalContrarianEngine.Input(
                options = options,
                volumeAccumulation = InstitutionalContrarianEngine.Component(null, "UNKNOWN"),
                insiders = InstitutionalContrarianEngine.Component(null, "UNKNOWN"),
                futuresPositioning = InstitutionalContrarianEngine.Component(null, "UNKNOWN"),
                priceTrendConstructive = technicalScore >= 60.0,
                technicalScore = technicalScore.coerceIn(0.0, 100.0)
            )
        )
        return OptionAssessmentEntity(
            assessmentId = "$runId-${ticker.trim().uppercase()}",
            runId = runId,
            ticker = ticker.trim().uppercase(),
            status = options.status,
            coveragePct = options.coveragePct,
            putCallOiTotal = options.putCallOiTotal,
            putCallOiNearSpot = options.putCallOiNearSpot,
            callWallStrike = options.callWallStrike,
            putWallStrike = options.putWallStrike,
            callWallDistancePct = options.callWallDistancePct,
            putWallDistancePct = options.putWallDistancePct,
            oiConcentrationPct = options.oiConcentrationPct,
            volumeToOiRatio = options.volumeToOiRatio,
            ivSkewPutMinusCall = options.ivSkewPutMinusCall,
            gammaStatus = options.gammaStatus,
            bias = institutional.optionsBias,
            optionsScore = options.score,
            institutionalScore = institutional.adjustedInstitutionalScore,
            contrarianAdjustment = institutional.contrarianAdjustment,
            conflict = institutional.conflict,
            reasons = institutional.reasons.joinToString("|"),
            engineVersion = listOf(
                OptionMetricsEngine.VERSION,
                InstitutionalContrarianEngine.VERSION,
                VERSION
            ).joinToString("+"),
            capturedAtUtc = capturedAtUtc
        )
    }
}
