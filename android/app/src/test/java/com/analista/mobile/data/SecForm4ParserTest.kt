package com.analista.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

class SecForm4ParserTest {
    private val client = SecEdgarClient("Analista test contact@example.com")

    @Test
    fun parsesOpenMarketPurchaseAndSaleWithoutDerivativeNoise() {
        val rows = client.parseForm4(form4Fixture(), "000123-26-000001")

        assertEquals(2, rows.size)
        val purchase = rows.first()
        assertEquals("TEST", purchase.ticker)
        assertEquals("Jane Doe", purchase.ownerName)
        assertTrue(purchase.isDirector)
        assertFalse(purchase.isOfficer)
        assertEquals(LocalDate.of(2026, 7, 10), purchase.transactionDate)
        assertEquals("P", purchase.transactionCode)
        assertEquals("A", purchase.acquiredDisposedCode)
        assertEquals(1_000.0, purchase.shares ?: 0.0, 0.0)
        assertEquals(25.50, purchase.pricePerShare ?: 0.0, 0.0)
        assertEquals(25_500.0, purchase.transactionValue ?: 0.0, 0.0)
        assertEquals(5_000.0, purchase.sharesOwnedFollowing ?: 0.0, 0.0)
        assertEquals("D", purchase.directOrIndirect)

        val sale = rows.last()
        assertEquals("S", sale.transactionCode)
        assertEquals("D", sale.acquiredDisposedCode)
        assertEquals(500.0, sale.shares ?: 0.0, 0.0)
        assertEquals(13_000.0, sale.transactionValue ?: 0.0, 0.0)
    }

    @Test
    fun incompleteTransactionRemainsExplicitlyPartial() {
        val xml = """<ownershipDocument>
          <issuer><issuerTradingSymbol>TEST</issuerTradingSymbol></issuer>
          <nonDerivativeTable><nonDerivativeTransaction>
            <securityTitle><value>Common Stock</value></securityTitle>
            <transactionCoding><transactionCode>A</transactionCode></transactionCoding>
            <transactionAmounts><transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode></transactionAmounts>
          </nonDerivativeTransaction></nonDerivativeTable>
        </ownershipDocument>"""

        val row = client.parseForm4(xml).single()

        assertEquals("A", row.transactionCode)
        assertNull(row.shares)
        assertNull(row.pricePerShare)
        assertNull(row.transactionValue)
    }

    @Test(expected = Exception::class)
    fun rejectsXmlWithDoctype() {
        client.parseForm4("""<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><ownershipDocument>&xxe;</ownershipDocument>""")
    }

    private fun form4Fixture() = """<?xml version="1.0" encoding="UTF-8"?>
      <ownershipDocument>
        <issuer>
          <issuerCik>0000123456</issuerCik>
          <issuerTradingSymbol>TEST</issuerTradingSymbol>
        </issuer>
        <reportingOwner>
          <reportingOwnerId><rptOwnerName>Jane Doe</rptOwnerName></reportingOwnerId>
          <reportingOwnerRelationship>
            <isDirector>1</isDirector><isOfficer>0</isOfficer>
          </reportingOwnerRelationship>
        </reportingOwner>
        <nonDerivativeTable>
          <nonDerivativeTransaction>
            <securityTitle><value>Common Stock</value></securityTitle>
            <transactionDate><value>2026-07-10</value></transactionDate>
            <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
            <transactionAmounts>
              <transactionShares><value>1000</value></transactionShares>
              <transactionPricePerShare><value>25.50</value></transactionPricePerShare>
              <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
            </transactionAmounts>
            <postTransactionAmounts><sharesOwnedFollowingTransaction><value>5000</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
            <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>
          </nonDerivativeTransaction>
          <nonDerivativeTransaction>
            <securityTitle><value>Common Stock</value></securityTitle>
            <transactionDate><value>2026-07-11</value></transactionDate>
            <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
            <transactionAmounts>
              <transactionShares><value>500</value></transactionShares>
              <transactionPricePerShare><value>26.00</value></transactionPricePerShare>
              <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
            </transactionAmounts>
          </nonDerivativeTransaction>
        </nonDerivativeTable>
        <derivativeTable>
          <derivativeTransaction><transactionCoding><transactionCode>A</transactionCode></transactionCoding></derivativeTransaction>
        </derivativeTable>
      </ownershipDocument>"""
}
