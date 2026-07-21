package com.analista.mobile.domain

import com.analista.mobile.data.InsiderTransactionRegistry
import com.analista.mobile.data.SecEdgarClient
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate
import java.time.ZoneOffset

class InsiderAssessmentEngineTest {
    private val asOf = LocalDate.of(2026, 7, 21)

    @Test
    fun multipleOpenMarketPurchasesCreateBullishEvidence() {
        val result = InsiderAssessmentEngine.assess(
            transactions = listOf(
                transaction("Jane Doe", "P", "A", 4_000.0, 25.0, LocalDate.of(2026, 7, 10)),
                transaction("John Doe", "P", "A", 3_000.0, 30.0, LocalDate.of(2026, 7, 12))
            ),
            asOfDate = asOf
        )

        assertEquals("BULLISH_WITH_DATA", result.bias)
        assertEquals("COMPLETE", result.coverageStatus)
        assertEquals(2, result.purchaseCount)
        assertEquals(2, result.distinctBuyerCount)
        assertTrue((result.score ?: 0.0) >= 60.0)
        assertTrue("sec_multiple_distinct_buyers" in result.reasons)
        assertTrue("sec_purchase_value_material" in result.reasons)
    }

    @Test
    fun saleOnlyIsModeratelyBearishNotAnAutomaticExtreme() {
        val result = InsiderAssessmentEngine.assess(
            transactions = listOf(
                transaction("Officer", "S", "D", 10_000.0, 20.0, LocalDate.of(2026, 7, 15))
            ),
            asOfDate = asOf
        )

        assertEquals("BEARISH_WITH_DATA", result.bias)
        assertTrue((result.score ?: 0.0) >= 30.0)
        assertTrue((result.score ?: 100.0) <= 40.0)
        assertTrue("sec_sales_are_context_not_hard_veto" in result.reasons)
    }

    @Test
    fun grantsAndTaxWithholdingAreIgnoredAsDirectionalEvidence() {
        val result = InsiderAssessmentEngine.assess(
            transactions = listOf(
                transaction("Officer", "A", "A", 2_000.0, null, LocalDate.of(2026, 7, 10)),
                transaction("Officer", "F", "D", 500.0, 20.0, LocalDate.of(2026, 7, 11))
            ),
            asOfDate = asOf
        )

        assertNull(result.score)
        assertEquals("UNKNOWN_INSIDER_FLOW", result.bias)
        assertEquals("EMPTY", result.coverageStatus)
        assertTrue("non_directional_form4_transactions_ignored" in result.reasons)
    }

    @Test
    fun transactionsOutsideLookbackDoNotAffectScore() {
        val result = InsiderAssessmentEngine.assess(
            transactions = listOf(
                transaction("Director", "P", "A", 5_000.0, 25.0, LocalDate.of(2026, 5, 1))
            ),
            asOfDate = asOf,
            lookbackDays = 35
        )

        assertNull(result.score)
        assertEquals(0, result.purchaseCount)
    }

    @Test
    fun registrySnapshotUsesCapturedDateDeterministically() {
        val captured = asOf.atStartOfDay().toInstant(ZoneOffset.UTC).toEpochMilli()
        val snapshot = InsiderTransactionRegistry.Snapshot(
            ticker = "TEST",
            transactions = listOf(transaction("Director", "P", "A", 2_000.0, 25.0, LocalDate.of(2026, 7, 20))),
            status = "COMPLETE",
            capturedAtUtc = captured
        )

        val result = InsiderAssessmentEngine.assess(snapshot)

        assertEquals("BULLISH_WITH_DATA", result.bias)
        assertEquals(50_000.0, result.purchaseValue, 0.0)
    }

    private fun transaction(
        owner: String,
        code: String,
        acquiredDisposed: String,
        shares: Double,
        price: Double?,
        date: LocalDate
    ) = SecEdgarClient.InsiderTransaction(
        accessionNumber = "fixture-$owner-$code",
        ticker = "TEST",
        ownerName = owner,
        isDirector = true,
        isOfficer = false,
        officerTitle = null,
        securityTitle = "Common Stock",
        transactionDate = date,
        transactionCode = code,
        acquiredDisposedCode = acquiredDisposed,
        shares = shares,
        pricePerShare = price,
        transactionValue = price?.let { shares * it },
        sharesOwnedFollowing = 10_000.0,
        directOrIndirect = "D"
    )
}
