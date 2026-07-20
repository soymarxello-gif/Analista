package com.analista.mobile.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZonedDateTime

class NyseSessionCalendarTest {
    @Test
    fun official2026HolidaysAreClosed() {
        listOf(
            LocalDate.of(2026, 1, 19),
            LocalDate.of(2026, 4, 3),
            LocalDate.of(2026, 6, 19),
            LocalDate.of(2026, 7, 3),
            LocalDate.of(2026, 11, 26),
            LocalDate.of(2026, 12, 25)
        ).forEach { date ->
            assertFalse("$date should be closed", NyseSessionCalendar.session(date).isTradingSession)
        }
    }

    @Test
    fun dayAfterThanksgivingAndChristmasEveCloseAtOnePmIn2026() {
        listOf(LocalDate.of(2026, 11, 27), LocalDate.of(2026, 12, 24)).forEach { date ->
            val session = NyseSessionCalendar.session(date)
            assertTrue(session.isTradingSession)
            assertTrue(session.earlyClose)
            assertEquals(LocalTime.of(13, 0), session.closeTimeEt)
        }
    }

    @Test
    fun latestCompletedSessionUsesEarlyCloseCutoff() {
        val beforeCutoff = ZonedDateTime.of(2026, 11, 27, 13, 10, 0, 0, NyseSessionCalendar.zoneId)
        val afterCutoff = beforeCutoff.withHour(13).withMinute(16)
        assertEquals(LocalDate.of(2026, 11, 25), NyseSessionCalendar.latestCompletedSession(beforeCutoff))
        assertEquals(LocalDate.of(2026, 11, 27), NyseSessionCalendar.latestCompletedSession(afterCutoff))
    }

    @Test
    fun holidayWeekendDoesNotCountAsMissingSessions() {
        val start = LocalDate.of(2026, 7, 2)
        val monday = LocalDate.of(2026, 7, 6)
        assertEquals(1, NyseSessionCalendar.sessionsBetween(start, monday))
        assertEquals(monday, NyseSessionCalendar.nextTradingSession(LocalDate.of(2026, 7, 3)))
    }

    @Test
    fun everySessionCarriesVersion() {
        assertEquals(NyseSessionCalendar.VERSION, NyseSessionCalendar.session(LocalDate.of(2026, 7, 6)).calendarVersion)
    }
}
