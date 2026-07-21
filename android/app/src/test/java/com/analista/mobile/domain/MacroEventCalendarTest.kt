package com.analista.mobile.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZoneId
import java.time.ZonedDateTime

class MacroEventCalendarTest {
    private val et = ZoneId.of("America/New_York")

    @Test
    fun fomcDecisionDayIsImminentAtPremarketScan() {
        val result = MacroEventCalendar.assess(atEt(2026, 7, 29, 9, 20))

        assertEquals("IMMINENT", result.risk)
        assertEquals("COMPLETE", result.scheduleCoverage)
        assertEquals("FOMC_DECISION", result.nearestEventType)
        assertTrue((result.hoursToNearestEvent ?: 100.0) in 4.0..5.0)
    }

    @Test
    fun dayBeforeFomcIsNear() {
        val result = MacroEventCalendar.assess(atEt(2026, 7, 28, 9, 20))

        assertEquals("NEAR", result.risk)
        assertEquals("FOMC_DECISION", result.nearestEventType)
    }

    @Test
    fun employmentReleaseRemainsImminentShortlyAfterPublication() {
        val result = MacroEventCalendar.assess(atEt(2026, 8, 7, 9, 20))

        assertEquals("IMMINENT", result.risk)
        assertEquals("EMPLOYMENT_SITUATION", result.nearestEventType)
        assertTrue((result.hoursToNearestEvent ?: 10.0) < 0.0)
    }

    @Test
    fun clearWindowUsesCompletePublishedSchedule() {
        val result = MacroEventCalendar.assess(atEt(2026, 7, 21, 9, 20))

        assertEquals("CLEAR", result.risk)
        assertEquals("COMPLETE", result.scheduleCoverage)
        assertTrue("macro_event_window_clear" in result.reasons)
    }

    @Test
    fun yearWithOnlyFomcScheduleRemainsUnknownOutsideFedWindow() {
        val result = MacroEventCalendar.assess(atEt(2027, 2, 10, 9, 20))

        assertEquals("UNKNOWN", result.risk)
        assertEquals("PARTIAL_FOMC_ONLY", result.scheduleCoverage)
        assertTrue("bls_schedule_not_published_for_year" in result.reasons)
    }

    @Test
    fun unsupportedYearDoesNotInventSchedule() {
        val result = MacroEventCalendar.assess(atEt(2028, 1, 10, 9, 20))

        assertEquals("UNKNOWN", result.risk)
        assertEquals("UNKNOWN", result.scheduleCoverage)
    }

    private fun atEt(year: Int, month: Int, day: Int, hour: Int, minute: Int): Long =
        ZonedDateTime.of(year, month, day, hour, minute, 0, 0, et).toInstant().toEpochMilli()
}
