package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

class CanonicalIndicatorParityTest {
    @Test
    fun androidCanonicalIndicatorsMatchSharedGoldenFixture() {
        val resource = checkNotNull(javaClass.classLoader?.getResourceAsStream("canonical_indicator_parity.json"))
        val root = JSONObject(resource.bufferedReader().use { it.readText() })
        val closeArray = root.getJSONArray("closes")
        val closes = (0 until closeArray.length()).map(closeArray::getDouble)
        val highOffset = root.getDouble("highOffset")
        val lowOffset = root.getDouble("lowOffset")
        val openOffset = root.getDouble("openOffset")
        val bars = closes.mapIndexed { index, close ->
            PriceBar(
                epochSeconds = 1_700_000_000L + index * 86_400L,
                open = close + openOffset,
                high = close + highOffset,
                low = close - lowOffset,
                close = close,
                volume = 1_000_000L + index * 1_000L
            )
        }
        val expected = root.getJSONObject("expected")
        val tolerance = root.getDouble("tolerance")
        val (macd, macdSignal) = CanonicalAnalysisEngine.macd(closes)

        assertEquals(expected.getDouble("rsi6"), CanonicalAnalysisEngine.rsiWilder(closes, 6), tolerance)
        assertEquals(expected.getDouble("rsi14"), CanonicalAnalysisEngine.rsiWilder(closes, 14), tolerance)
        assertEquals(expected.getDouble("ema20"), CanonicalAnalysisEngine.emaLast(closes, 20), tolerance)
        assertEquals(expected.getDouble("ema50"), CanonicalAnalysisEngine.emaLast(closes, 50), tolerance)
        assertEquals(expected.getDouble("atr14"), CanonicalAnalysisEngine.atrWilder(bars, 14), tolerance)
        assertEquals(expected.getDouble("macd"), macd, tolerance)
        assertEquals(expected.getDouble("macdSignal"), macdSignal, tolerance)
    }
}
