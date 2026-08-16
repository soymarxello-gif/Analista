package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import com.analista.mobile.data.SignalContractEntity
import com.analista.mobile.data.TradeOutcomeEntity
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.round

object BacktestEngine {
    const val VERSION = "backtest-fill-3"

    data class CostModel(
        val entrySlippageBps: Double = 5.0,
        val exitSlippageBps: Double = 5.0,
        val commissionPerShare: Double = 0.0,
        val version: String = "cost-model-1"
    ) {
        init {
            require(entrySlippageBps >= 0.0)
            require(exitSlippageBps >= 0.0)
            require(commissionPerShare >= 0.0)
        }
    }

    private data class Entry(
        val index: Int,
        val fill: Double,
        val triggeredAtUtc: Long,
        val triggeredAtOpen: Boolean
    )

    private data class Exit(
        val index: Int,
        val timestampUtc: Long,
        val fill: Double?,
        val reason: String,
        val stopHit: Boolean,
        val targetHit: Boolean,
        val ambiguous: Boolean
    )

    private data class Excursions(
        val mfePct: Double?,
        val maePct: Double?
    )

    fun evaluate(
        contract: SignalContractEntity,
        bars: List<PriceBar>,
        evaluatedAtUtc: Long = System.currentTimeMillis(),
        costs: CostModel = CostModel()
    ): TradeOutcomeEntity {
        require(contract.triggerPrice > contract.stopPrice)
        require(contract.targetPrice > contract.triggerPrice)
        require(contract.maximumEntry >= contract.triggerPrice)

        // expirationSessions is the decision-window lifetime of the immutable signal contract.
        // A late fill does not restart that clock: the trade expires at the end of the same
        // decision window. This keeps triggered and non-triggered contracts on one timeline.
        val future = bars.filter { it.epochSeconds * 1000L > contract.decisionTimestampUtc }
            .take(contract.expirationSessions)
        val entry = findEntry(contract, future, costs)
            ?: return emptyOutcome(contract, evaluatedAtUtc, future.size, costs.version)
        val active = future.drop(entry.index)
        val exit = findExit(contract, active, entry, costs)

        val decisionWindowComplete = future.size >= contract.expirationSessions
        val resolvedExit = exit ?: if (decisionWindowComplete && active.isNotEmpty()) {
            val lastIndex = active.lastIndex
            val last = active[lastIndex]
            Exit(
                index = lastIndex,
                timestampUtc = last.epochSeconds * 1000L,
                fill = sellFill(last.close, costs.exitSlippageBps),
                reason = "EXPIRED",
                stopHit = false,
                targetHit = false,
                ambiguous = false
            )
        } else null
        val observed = active.take((resolvedExit?.index?.plus(1)) ?: active.size)
        val excursions = excursions(observed, entry, resolvedExit)

        fun markout(days: Int): Double? = active.getOrNull(days - 1)?.close
            ?.let { round2((it / entry.fill - 1.0) * 100.0) }

        val exitFill = resolvedExit?.fill
        val tradeReturnPct = exitFill?.let { round2((it / entry.fill - 1.0) * 100.0) }
        val riskPerShare = entry.fill - contract.stopPrice
        val tradeReturnR = if (exitFill != null && riskPerShare > 0.0) {
            round2((exitFill - entry.fill) / riskPerShare)
        } else null
        val resolvedShares = when {
            contract.shares > 0 -> contract.shares
            contract.positionValue > 0.0 -> floor(contract.positionValue / entry.fill).toInt().coerceAtLeast(0)
            else -> 0
        }
        val totalCosts = if (resolvedShares > 0 && exitFill != null) {
            round2(resolvedShares * costs.commissionPerShare * 2.0)
        } else null
        val grossPnl = if (resolvedShares > 0 && exitFill != null) {
            round2((exitFill - entry.fill) * resolvedShares)
        } else null
        val netPnl = if (grossPnl != null) round2(grossPnl - (totalCosts ?: 0.0)) else null

        val status = when {
            resolvedExit?.ambiguous == true -> "CLOSED_AMBIGUOUS"
            resolvedExit?.reason == "TARGET" || resolvedExit?.reason == "GAP_TARGET" -> "CLOSED_TARGET"
            resolvedExit?.reason == "STOP" || resolvedExit?.reason == "GAP_STOP" -> "CLOSED_STOP"
            resolvedExit?.reason == "EXPIRED" -> "CLOSED_EXPIRED"
            else -> "OPEN"
        }

        return TradeOutcomeEntity(
            signalId = contract.signalId,
            ticker = contract.ticker,
            evaluatedAtUtc = evaluatedAtUtc,
            triggered = true,
            triggerTimestampUtc = entry.triggeredAtUtc,
            entryFill = round2(entry.fill),
            stopHit = resolvedExit?.stopHit ?: false,
            targetHit = resolvedExit?.targetHit ?: false,
            firstExitEvent = resolvedExit?.reason ?: "NONE",
            return1dPct = markout(1),
            return3dPct = markout(3),
            return5dPct = markout(5),
            return10dPct = markout(10),
            return20dPct = markout(20),
            mfePct = excursions.mfePct?.let(::round2),
            maePct = excursions.maePct?.let(::round2),
            holdingSessions = observed.size,
            ambiguousSameBar = resolvedExit?.ambiguous ?: false,
            status = status,
            exitTimestampUtc = resolvedExit?.timestampUtc,
            exitFill = exitFill?.let(::round2),
            exitReason = resolvedExit?.reason ?: "NONE",
            tradeReturnPct = tradeReturnPct,
            tradeReturnR = tradeReturnR,
            grossPnl = grossPnl,
            netPnl = netPnl,
            totalCosts = totalCosts,
            costModelVersion = costs.version
        )
    }

    private fun excursions(
        observed: List<PriceBar>,
        entry: Entry,
        resolvedExit: Exit?
    ): Excursions {
        if (observed.isEmpty()) return Excursions(null, null)

        // With daily OHLC we cannot know whether the entry-bar low happened before or after
        // an intraday trigger. Do not manufacture adverse excursion from pre-entry prices.
        // If the same entry bar also touches the stop, the path itself is indeterminate and
        // both excursion metrics are withheld rather than leaking an assumed intrabar order.
        if (!entry.triggeredAtOpen && resolvedExit?.index == 0 && resolvedExit.ambiguous) {
            return Excursions(null, null)
        }

        val mfe = observed.maxOfOrNull { (it.high / entry.fill - 1.0) * 100.0 }
        val mae = if (entry.triggeredAtOpen) {
            observed.minOfOrNull { (it.low / entry.fill - 1.0) * 100.0 }
        } else {
            val laterMae = observed.drop(1).minOfOrNull { (it.low / entry.fill - 1.0) * 100.0 }
            minOf(0.0, laterMae ?: 0.0)
        }
        return Excursions(mfe, mae)
    }

    private fun findEntry(
        contract: SignalContractEntity,
        future: List<PriceBar>,
        costs: CostModel
    ): Entry? {
        for ((index, bar) in future.withIndex()) {
            if (bar.open > contract.maximumEntry) continue
            if (bar.high < contract.triggerPrice) continue
            val rawFill = max(bar.open, contract.triggerPrice)
            val effectiveFill = buyFill(rawFill, costs.entrySlippageBps)
            if (effectiveFill > contract.maximumEntry) continue
            return Entry(
                index = index,
                fill = effectiveFill,
                triggeredAtUtc = bar.epochSeconds * 1000L,
                triggeredAtOpen = bar.open >= contract.triggerPrice
            )
        }
        return null
    }

    private fun findExit(
        contract: SignalContractEntity,
        active: List<PriceBar>,
        entry: Entry,
        costs: CostModel
    ): Exit? {
        for ((index, bar) in active.withIndex()) {
            val firstBar = index == 0
            val touchesStop = bar.low <= contract.stopPrice
            val touchesTarget = bar.high >= contract.targetPrice

            if (firstBar && !entry.triggeredAtOpen && touchesStop) {
                return Exit(
                    index = index,
                    timestampUtc = bar.epochSeconds * 1000L,
                    fill = null,
                    reason = if (touchesTarget) "AMBIGUOUS_SAME_BAR" else "AMBIGUOUS_ENTRY_STOP_SAME_BAR",
                    stopHit = true,
                    targetHit = touchesTarget,
                    ambiguous = true
                )
            }
            if (bar.open <= contract.stopPrice) {
                return Exit(index, bar.epochSeconds * 1000L, sellFill(bar.open, costs.exitSlippageBps), "GAP_STOP", true, false, false)
            }
            if (bar.open >= contract.targetPrice) {
                return Exit(index, bar.epochSeconds * 1000L, sellFill(bar.open, costs.exitSlippageBps), "GAP_TARGET", false, true, false)
            }
            if (touchesStop && touchesTarget) {
                return Exit(index, bar.epochSeconds * 1000L, null, "AMBIGUOUS_SAME_BAR", true, true, true)
            }
            if (touchesStop) {
                return Exit(index, bar.epochSeconds * 1000L, sellFill(contract.stopPrice, costs.exitSlippageBps), "STOP", true, false, false)
            }
            if (touchesTarget) {
                return Exit(index, bar.epochSeconds * 1000L, sellFill(contract.targetPrice, costs.exitSlippageBps), "TARGET", false, true, false)
            }
        }
        return null
    }

    private fun emptyOutcome(
        contract: SignalContractEntity,
        evaluatedAtUtc: Long,
        sessions: Int,
        costModelVersion: String
    ) = TradeOutcomeEntity(
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
        status = if (sessions >= contract.expirationSessions) "EXPIRED_NOT_TRIGGERED" else "NOT_TRIGGERED",
        exitReason = "NONE",
        costModelVersion = costModelVersion
    )

    private fun buyFill(price: Double, bps: Double) = price * (1.0 + bps / 10_000.0)
    private fun sellFill(price: Double, bps: Double) = price * (1.0 - bps / 10_000.0)
    private fun round2(value: Double) = round(value * 100.0) / 100.0
}
