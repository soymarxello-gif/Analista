package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import com.analista.mobile.data.SignalContractEntity
import com.analista.mobile.data.TradeOutcomeEntity
import kotlin.math.max
import kotlin.math.round

object BacktestEngine {
    const val VERSION = "backtest-fills-costs-1"

    data class CostModel(
        val entrySlippageBps: Double = 5.0,
        val stopSlippageBps: Double = 10.0,
        val marketExitSlippageBps: Double = 5.0,
        val commissionPerShareUsd: Double = 0.005,
        val minimumCommissionPerSideUsd: Double = 1.0,
        val version: String = "cost-model-1"
    ) {
        init {
            require(entrySlippageBps >= 0.0)
            require(stopSlippageBps >= 0.0)
            require(marketExitSlippageBps >= 0.0)
            require(commissionPerShareUsd >= 0.0)
            require(minimumCommissionPerSideUsd >= 0.0)
        }
    }

    private data class Entry(
        val index: Int,
        val rawPrice: Double,
        val fillPrice: Double,
        val gapAtOpen: Boolean
    )

    private data class Exit(
        val index: Int,
        val rawPrice: Double?,
        val fillPrice: Double?,
        val reason: String,
        val stopHit: Boolean,
        val targetHit: Boolean,
        val ambiguous: Boolean
    )

    fun evaluate(
        contract: SignalContractEntity,
        bars: List<PriceBar>,
        evaluatedAtUtc: Long = System.currentTimeMillis(),
        costs: CostModel = CostModel()
    ): TradeOutcomeEntity {
        require(contract.shares > 0)
        val future = bars.filter { it.epochSeconds * 1000L > contract.decisionTimestampUtc }
            .take(contract.expirationSessions)
        val entry = findEntry(contract, future, costs)
            ?: return emptyOutcome(contract, evaluatedAtUtc, future.size, costs)

        val active = future.drop(entry.index)
        val exit = findExit(contract, active, entry, costs)
        val observedCount = when {
            exit != null -> exit.index + 1
            else -> active.size
        }
        val observed = active.take(observedCount)
        val mfe = observed.maxOfOrNull { (it.high / entry.fillPrice - 1.0) * 100.0 }
        val mae = observed.minOfOrNull { (it.low / entry.fillPrice - 1.0) * 100.0 }
        val status = when {
            exit?.ambiguous == true -> "CLOSED_AMBIGUOUS"
            exit?.targetHit == true -> "CLOSED_TARGET"
            exit?.stopHit == true -> "CLOSED_STOP"
            exit?.reason == "EXPIRATION" -> "EXPIRED"
            future.size >= contract.expirationSessions -> "EXPIRED"
            else -> "OPEN"
        }
        fun markout(days: Int): Double? = active.getOrNull(days - 1)?.close?.let {
            round2((it / entry.fillPrice - 1.0) * 100.0)
        }

        val exitPrice = exit?.fillPrice
        val commission = if (exitPrice != null && !exit.ambiguous) commission(contract.shares, costs) else 0.0
        val grossPnl = exitPrice?.takeUnless { exit.ambiguous }?.let {
            (it - entry.fillPrice) * contract.shares
        }
        val netPnl = grossPnl?.let { it - commission }
        val invested = entry.fillPrice * contract.shares
        val tradeReturnPct = netPnl?.takeIf { invested > 0.0 }?.let { it / invested * 100.0 }
        val initialRisk = (entry.fillPrice - contract.stopPrice) * contract.shares
        val returnR = netPnl?.takeIf { initialRisk > 0.0 }?.let { it / initialRisk }
        val exitTimestamp = exit?.takeIf { it.fillPrice != null }?.let { active[it.index].epochSeconds * 1000L }
        val entrySlippagePct = (entry.fillPrice / entry.rawPrice - 1.0) * 100.0
        val exitSlippagePct = if (exit?.rawPrice != null && exit.fillPrice != null && exit.rawPrice > 0.0) {
            (exit.fillPrice / exit.rawPrice - 1.0) * 100.0
        } else null

        return TradeOutcomeEntity(
            signalId = contract.signalId,
            ticker = contract.ticker,
            evaluatedAtUtc = evaluatedAtUtc,
            triggered = true,
            triggerTimestampUtc = future[entry.index].epochSeconds * 1000L,
            entryFill = round2(entry.fillPrice),
            stopHit = exit?.stopHit == true,
            targetHit = exit?.targetHit == true,
            firstExitEvent = exit?.reason ?: "NONE",
            return1dPct = markout(1),
            return3dPct = markout(3),
            return5dPct = markout(5),
            return10dPct = markout(10),
            return20dPct = markout(20),
            mfePct = mfe?.let(::round2),
            maePct = mae?.let(::round2),
            holdingSessions = observed.size,
            ambiguousSameBar = exit?.ambiguous == true,
            status = status,
            exitPrice = exitPrice?.let(::round2),
            exitTimestampUtc = exitTimestamp,
            exitReason = exit?.reason ?: "NONE",
            entrySlippagePct = round4(entrySlippagePct),
            exitSlippagePct = exitSlippagePct?.let(::round4),
            commissionUsd = round2(commission),
            grossPnlUsd = grossPnl?.let(::round2),
            netPnlUsd = netPnl?.let(::round2),
            tradeReturnPct = tradeReturnPct?.let(::round4),
            returnR = returnR?.let(::round4),
            costModelVersion = "${VERSION}+${costs.version}"
        )
    }

    private fun findEntry(
        contract: SignalContractEntity,
        future: List<PriceBar>,
        costs: CostModel
    ): Entry? {
        for ((index, bar) in future.withIndex()) {
            if (bar.open > contract.maximumEntry || bar.high < contract.triggerPrice) continue
            val raw = max(bar.open, contract.triggerPrice)
            val fill = raw * (1.0 + costs.entrySlippageBps / 10_000.0)
            if (fill <= contract.maximumEntry) {
                return Entry(index, raw, fill, bar.open >= contract.triggerPrice)
            }
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
            val touchesStop = bar.low <= contract.stopPrice
            val touchesTarget = bar.high >= contract.targetPrice
            if (touchesStop && touchesTarget) {
                return Exit(index, null, null, "AMBIGUOUS_SAME_BAR", true, true, true)
            }
            if (index == 0 && touchesStop && !entry.gapAtOpen) {
                return Exit(index, null, null, "AMBIGUOUS_ENTRY_STOP_SAME_BAR", true, false, true)
            }
            if (bar.open <= contract.stopPrice) {
                val fill = bar.open * (1.0 - costs.stopSlippageBps / 10_000.0)
                return Exit(index, bar.open, fill, "STOP_GAP", true, false, false)
            }
            if (bar.open >= contract.targetPrice) {
                val slipped = bar.open * (1.0 - costs.marketExitSlippageBps / 10_000.0)
                val fill = max(contract.targetPrice, slipped)
                return Exit(index, bar.open, fill, "TARGET_GAP", false, true, false)
            }
            if (touchesStop) {
                val fill = contract.stopPrice * (1.0 - costs.stopSlippageBps / 10_000.0)
                return Exit(index, contract.stopPrice, fill, "STOP", true, false, false)
            }
            if (touchesTarget) {
                return Exit(index, contract.targetPrice, contract.targetPrice, "TARGET", false, true, false)
            }
        }
        if (active.size >= contract.expirationSessions && active.isNotEmpty()) {
            val index = active.lastIndex
            val raw = active[index].close
            val fill = raw * (1.0 - costs.marketExitSlippageBps / 10_000.0)
            return Exit(index, raw, fill, "EXPIRATION", false, false, false)
        }
        return null
    }

    private fun commission(shares: Int, costs: CostModel): Double {
        val oneSide = max(costs.minimumCommissionPerSideUsd, shares * costs.commissionPerShareUsd)
        return oneSide * 2.0
    }

    private fun emptyOutcome(
        contract: SignalContractEntity,
        evaluatedAtUtc: Long,
        sessions: Int,
        costs: CostModel
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
        costModelVersion = "${VERSION}+${costs.version}"
    )

    private fun round2(value: Double) = round(value * 100.0) / 100.0
    private fun round4(value: Double) = round(value * 10_000.0) / 10_000.0
}
