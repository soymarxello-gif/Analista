package com.analista.mobile.domain

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate
import java.time.ZoneId
import java.time.ZonedDateTime

class NyseCalendarTest {
    @Test fun rejectsWeekendAndKnownHolidays() { assertFalse(NyseCalendar.isSession(LocalDate.of(2026,7,4))); assertFalse(NyseCalendar.isSession(LocalDate.of(2026,12,25))); assertTrue(NyseCalendar.isSession(LocalDate.of(2026,7,20))) }
    @Test fun schedulesAtNineTwentyNewYorkAcrossDst() { val before = ZonedDateTime.of(2026,7,20,8,0,0,0, ZoneId.of("America/New_York")); val next = NyseCalendar.nextScheduled(before); assertTrue(next.hour == 9 && next.minute == 20); assertTrue(next.zone == ZoneId.of("America/New_York")) }
}
