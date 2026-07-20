package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MacroRegimeEngineTest {
    private fun bars(start: Double, dailyReturn: Double, count: Int = 80): List<PriceBar> {
        var close = start
        return (0 until count).map { index ->
            close *= 1.0 + dailyReturn
            PriceBar(index.toLong(), close, close * 1.01, close * 0.99, close, 1_000_000L)
        }
    }

    @Test
    fun broadUptrendLowVixAndStableRatesProduceRiskOn() {
        val histories = mapOf(
            "SPY" to bars(500.0, 0.0020),
            "QQQ" to bars(450.0, 0.0023),
            "IWM" to bars(200.0, 0.0017),
            "^VIX" to bars(22.0, -0.0030),
            "^TNX" to bars(4.2, 0.0001),
            "^TYX" to bars(4.5, 0.0001),
            "DX-Y.NYB" to bars(104.0, -0.0003),
            "CL=F" to bars(75.0, 0.0002),
            "BTC-USD" to bars(80_000.0, 0.0015)
        )
        val result = MacroRegimeEngine.assess(histories)
        assertEquals("RISK_ON", result.macroRegime)
        assertEquals("RISK_SEEKING", result.riskAppetite)
        assertEquals("HIGH", result.confidence)
        assertTrue(result.macroScore >= 65.0)
        assertEquals(100.0, result.coveragePct, 0.001)
    }

    @Test
    fun fallingEquitiesRisingVixRatesAndDollarProduceRiskOff() {
        val histories = mapOf(
            "SPY" to bars(500.0, -0.0030),
            "QQQ" to bars(450.0, -0.0035),
            "IWM" to bars(200.0, -0.0032),
            "^VIX" to bars(20.0, 0.0060),
            "^TNX" to bars(4.0, 0.0030),
            "^TYX" to bars(4.3, 0.0025),
            "DX-Y.NYB" to bars(100.0, 0.0020),
            "CL=F" to bars(70.0, 0.0030),
            "BTC-USD" to bars(80_000.0, -0.0040)
        )
        val result = MacroRegimeEngine.assess(histories)
        assertEquals("RISK_OFF", result.macroRegime)
        assertEquals("RISK_AVERSE", result.riskAppetite)
        assertEquals("RISING", result.ratesRegime)
        assertTrue(result.macroScore <= 35.0)
    }

    @Test
    fun missingHistoryIsNotAssumedNeutral() {
        val result = MacroRegimeEngine.assess(emptyMap())
        assertEquals("UNKNOWN", result.confidence)
        assertEquals("UNKNOWN", result.riskAppetite)
        assertEquals("UNKNOWN", result.liquidityRegime)
        assertTrue("liquidity_series_unavailable" in result.reasons)
    }
}
