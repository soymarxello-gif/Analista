package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate
import java.time.ZoneId
import java.time.ZonedDateTime

class DataQualityEngineTest {
    private val zone = ZoneId.of("America/New_York")

    @Test
    fun mondayPremarketAcceptsFridayAsLatestCompletedSession() {
        val friday = LocalDate.of(2026, 7, 17)
        val now = ZonedDateTime.of(2026, 7, 20, 9, 20, 0, 0, zone).toInstant().toEpochMilli()
        val result = DataQualityEngine.assess(barsEnding(friday), cacheHit = false, nowMillis = now)
        assertEquals(0, result.sessionsOld)
        assertEquals("HIGH", result.status)
        assertTrue(result.executionAllowed)
    }

    @Test
    fun oneMissingSessionBlocksExecutionButRemainsObservable() {
        val monday = LocalDate.of(2026, 7, 20)
        val now = ZonedDateTime.of(2026, 7, 22, 9, 20, 0, 0, zone).toInstant().toEpochMilli()
        val result = DataQualityEngine.assess(barsEnding(monday), cacheHit = false, nowMillis = now)
        assertEquals(1, result.sessionsOld)
        assertEquals("LOW", result.status)
        assertFalse(result.executionAllowed)
        assertTrue("missing_latest_session" in result.reasons)
    }

    @Test
    fun multipleMissingSessionsAreUnusable() {
        val monday = LocalDate.of(2026, 7, 20)
        val now = ZonedDateTime.of(2026, 7, 23, 9, 20, 0, 0, zone).toInstant().toEpochMilli()
        val result = DataQualityEngine.assess(barsEnding(monday), cacheHit = true, nowMillis = now)
        assertEquals("UNUSABLE", result.status)
        assertFalse(result.executionAllowed)
    }

    @Test
    fun insufficientDollarLiquidityBlocksExecution() {
        val friday = LocalDate.of(2026, 7, 17)
        val now = ZonedDateTime.of(2026, 7, 20, 9, 20, 0, 0, zone).toInstant().toEpochMilli()
        val result = DataQualityEngine.assess(barsEnding(friday, volume = 1_000), cacheHit = false, nowMillis = now)
        assertEquals("LOW", result.status)
        assertTrue("dollar_volume_below_min" in result.reasons)
    }

    private fun barsEnding(end: LocalDate, volume: Long = 1_000_000L): List<PriceBar> = (0 until 220).map { offset ->
        val date = end.minusDays((219 - offset).toLong())
        val epoch = date.atTime(16, 0).atZone(zone).toEpochSecond()
        val close = 100.0 + offset * 0.1
        PriceBar(epoch, close - 1.0, close + 1.0, close - 2.0, close, volume)
    }
}
