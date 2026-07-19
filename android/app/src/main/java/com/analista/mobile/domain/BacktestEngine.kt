package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import com.analista.mobile.data.SignalContractEntity
import com.analista.mobile.data.TradeOutcomeEntity
import kotlin.math.max
import kotlin.math.round

object BacktestEngine {
    fun evaluate(
        contract: SignalContractEntity,
        bars: List<PriceBar>,
        evaluatedAtUtc: Long = System.currentTimeMillis()
    ): TradeOutcomeEntity {
        val future = bars.filter { it.epochSeconds * 1000L > contract.decisionTimestampUtc }
            .take(contract.expirationSessions)
        var triggerIndex: Int? = null
        var fill: Double? = null
        for ((index, bar) in future.withIndex()) {
            if (bar.open > contract.maximumEntry) continue
            if (bar.high >= contract.triggerPrice) {
                val proposed = max(bar.open, contract.triggerPrice)
                if (proposed <= contract.maximumEntry) {
                    triggerIndex = index
                    fill = proposed
                    break
                }
            }
        }
        if (triggerIndex == null || fill == null) {
            return emptyOutcome(contract, evaluatedAtUtc, future.size)
        }

        val active = future.drop(triggerIndex)
        var stopHit = false
        var targetHit = false
        var ambiguous = false
        var firstEvent = "NONE"
        var exitIndex: Int? = null
        for ((index, bar) in active.withIndex()) {
            val touchesStop = bar.low <= contract.stopPrice
            val touchesTarget = bar.high >= contract.targetPrice
            if (touchesStop && touchesTarget) {
                stopHit = true
                targetHit = true
                ambiguous = true
                firstEvent = "AMBIGUOUS_SAME_BAR"
                exitIndex = index
                break
            }
            if (touchesStop) {
                stopHit = true
                firstEvent = "STOP"
                exitIndex = index
                break
            }
            if (touchesTarget) {
                targetHit = true
                firstEvent = "TARGET"
                exitIndex = index
                break
            }
        }

        val observed = active.take((exitIndex?.plus(1)) ?: active.size)
        val mfe = observed.maxOfOrNull { (it.high / fill - 1.0) * 100.0 }
        val mae = observed.minOfOrNull { (it.low / fill - 1.0) * 100.0 }
        val status = when {
            ambiguous -> "CLOSED_AMBIGUOUS"
            targetHit -> "CLOSED_TARGET"
            stopHit -> "CLOSED_STOP"
            future.size >= contract.expirationSessions -> "EXPIRED"
            else -> "OPEN"
        }
        fun horizonReturn(days: Int): Double? = active.getOrNull(days - 1)?.close?.let { round2((it / fill - 1.0) * 100.0) }

        return TradeOutcomeEntity(
            signalId = contract.signalId,
            ticker = contract.ticker,
            evaluatedAtUtc = evaluatedAtUtc,
            triggered = true,
            triggerTimestampUtc = future[triggerIndex].epochSeconds * 1000L,
            entryFill = round2(fill),
            stopHit = stopHit,
            targetHit = targetHit,
            firstExitEvent = firstEvent,
            return1dPct = horizonReturn(1),
            return3dPct = horizonReturn(3),
            return5dPct = horizonReturn(5),
            return10dPct = horizonReturn(10),
            return20dPct = horizonReturn(20),
            mfePct = mfe?.let(::round2),
            maePct = mae?.let(::round2),
            holdingSessions = observed.size,
            ambiguousSameBar = ambiguous,
            status = status
        )
    }

    private fun emptyOutcome(contract: SignalContractEntity, evaluatedAtUtc: Long, sessions: Int) = TradeOutcomeEntity(
        signalId = contract.signalId,
        ticker = contract.ticker,
        evaluatedAtUtc = evaluatedAtUtc,
        triggered = false,
        triggerTimestampUtc = null,
        entryFill = null,
        stopHit = false,
        targetHit = false,
        firstExitEvent = "NONE",
        return1dPct = null,
        return3dPct = null,
        return5dPct = null,
        return10dPct = null,
        return20dPct = null,
        mfePct = null,
        maePct = null,
        holdingSessions = sessions,
        ambiguousSameBar = false,
        status = if (sessions >= contract.expirationSessions) "EXPIRED_NOT_TRIGGERED" else "NOT_TRIGGERED"
    )

    private fun round2(value: Double) = round(value * 100.0) / 100.0
}
