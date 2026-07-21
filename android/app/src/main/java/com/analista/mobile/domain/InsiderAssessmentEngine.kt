package com.analista.mobile.domain

import com.analista.mobile.data.InsiderTransactionRegistry
import com.analista.mobile.data.SecEdgarClient
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import kotlin.math.round

object InsiderAssessmentEngine {
    const val VERSION = "insider-assessment-1"

    data class Assessment(
        val score: Double?,
        val bias: String,
        val coverageStatus: String,
        val purchaseCount: Int,
        val saleCount: Int,
        val distinctBuyerCount: Int,
        val purchaseValue: Double,
        val saleValue: Double,
        val reasons: List<String>,
        val engineVersion: String = VERSION
    )

    fun assess(
        snapshot: InsiderTransactionRegistry.Snapshot?,
        lookbackDays: Long = 35L
    ): Assessment {
        require(lookbackDays in 1L..180L)
        if (snapshot == null) return unknown("sec_insider_transactions_not_loaded")
        if (snapshot.status.uppercase() in setOf("UNKNOWN", "UNAVAILABLE", "ERROR")) {
            return unknown("sec_insider_transactions_${snapshot.status.lowercase()}")
        }
        val asOfDate = Instant.ofEpochMilli(snapshot.capturedAtUtc).atZone(ZoneOffset.UTC).toLocalDate()
        return assess(snapshot.transactions, asOfDate, lookbackDays, snapshot.status)
    }

    fun assess(
        transactions: List<SecEdgarClient.InsiderTransaction>,
        asOfDate: LocalDate,
        lookbackDays: Long = 35L,
        sourceStatus: String = "COMPLETE"
    ): Assessment {
        require(lookbackDays in 1L..180L)
        val cutoff = asOfDate.minusDays(lookbackDays)
        val recent = transactions.filter { transaction ->
            val date = transaction.transactionDate
            date != null && !date.isBefore(cutoff) && !date.isAfter(asOfDate)
        }
        val directional = recent.filter(::isDirectional)
        if (directional.isEmpty()) {
            val reasons = mutableListOf("no_recent_open_market_insider_transactions")
            if (recent.isNotEmpty()) reasons += "non_directional_form4_transactions_ignored"
            return Assessment(
                score = null,
                bias = "UNKNOWN_INSIDER_FLOW",
                coverageStatus = if (sourceStatus.uppercase() == "PARTIAL") "PARTIAL" else "EMPTY",
                purchaseCount = 0,
                saleCount = 0,
                distinctBuyerCount = 0,
                purchaseValue = 0.0,
                saleValue = 0.0,
                reasons = reasons
            )
        }

        val purchases = directional.filter(::isPurchase)
        val sales = directional.filter(::isSale)
        val completeDirectional = directional.filter { transaction ->
            transaction.transactionValue?.let { it > 0.0 && it.isFinite() } == true
        }
        val coverageStatus = if (completeDirectional.size == directional.size) "COMPLETE" else "PARTIAL"
        val purchaseValue = purchases.sumOf(::weightedValue)
        val saleValue = sales.sumOf(::weightedValue)
        val buyerCount = purchases.mapNotNull { it.ownerName?.trim()?.uppercase()?.takeIf(String::isNotBlank) }.distinct().size
        val reasons = mutableListOf<String>()
        if (purchases.isNotEmpty()) reasons += "sec_open_market_purchases_present"
        if (sales.isNotEmpty()) reasons += "sec_open_market_sales_present"
        if (buyerCount >= 2) reasons += "sec_multiple_distinct_buyers"
        if (purchaseValue >= 100_000.0) reasons += "sec_purchase_value_material"
        if (coverageStatus == "PARTIAL") reasons += "sec_transaction_values_partial"

        val score = if (purchaseValue > 0.0 || saleValue > 0.0) {
            val adjustedSales = 0.50 * saleValue
            val denominator = purchaseValue + adjustedSales
            val balance = if (denominator > 0.0) (purchaseValue - adjustedSales) / denominator else 0.0
            var value = 50.0 + 35.0 * balance
            if (buyerCount >= 2) value += 4.0
            if (purchaseValue >= 250_000.0) value += 3.0
            if (purchases.isEmpty() && sales.isNotEmpty()) value = value.coerceAtLeast(30.0)
            round2(value.coerceIn(25.0, 90.0))
        } else null

        val bias = when {
            score == null -> "UNKNOWN_INSIDER_FLOW"
            score >= 60.0 -> "BULLISH_WITH_DATA"
            score <= 40.0 -> "BEARISH_WITH_DATA"
            else -> "NEUTRAL_WITH_DATA"
        }
        if (bias == "BEARISH_WITH_DATA") reasons += "sec_sales_are_context_not_hard_veto"

        return Assessment(
            score = score,
            bias = bias,
            coverageStatus = coverageStatus,
            purchaseCount = purchases.size,
            saleCount = sales.size,
            distinctBuyerCount = buyerCount,
            purchaseValue = round2(purchaseValue),
            saleValue = round2(saleValue),
            reasons = reasons.distinct()
        )
    }

    private fun isDirectional(transaction: SecEdgarClient.InsiderTransaction): Boolean =
        isPurchase(transaction) || isSale(transaction)

    private fun isPurchase(transaction: SecEdgarClient.InsiderTransaction): Boolean =
        transaction.transactionCode?.uppercase() == "P" && transaction.acquiredDisposedCode?.uppercase() == "A"

    private fun isSale(transaction: SecEdgarClient.InsiderTransaction): Boolean =
        transaction.transactionCode?.uppercase() == "S" && transaction.acquiredDisposedCode?.uppercase() == "D"

    private fun weightedValue(transaction: SecEdgarClient.InsiderTransaction): Double {
        val raw = transaction.transactionValue?.takeIf { it.isFinite() && it > 0.0 } ?: return 0.0
        val ownershipWeight = if (transaction.directOrIndirect?.uppercase() == "I") 0.70 else 1.0
        return raw * ownershipWeight
    }

    private fun unknown(reason: String) = Assessment(
        score = null,
        bias = "UNKNOWN_INSIDER_FLOW",
        coverageStatus = "UNKNOWN",
        purchaseCount = 0,
        saleCount = 0,
        distinctBuyerCount = 0,
        purchaseValue = 0.0,
        saleValue = 0.0,
        reasons = listOf(reason)
    )

    private fun round2(value: Double) = round(value * 100.0) / 100.0
}
