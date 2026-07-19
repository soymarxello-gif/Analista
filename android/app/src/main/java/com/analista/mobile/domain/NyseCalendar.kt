package com.analista.mobile.domain

import java.time.*
import java.time.temporal.TemporalAdjusters

object NyseCalendar {
    val zone: ZoneId = ZoneId.of("America/New_York")
    val scheduledTime: LocalTime = LocalTime.of(9, 20)
    fun isSession(date: LocalDate) = date.dayOfWeek !in setOf(DayOfWeek.SATURDAY, DayOfWeek.SUNDAY) && date !in holidays(date.year)
    fun nextScheduled(after: ZonedDateTime = ZonedDateTime.now()): ZonedDateTime {
        val ny = after.withZoneSameInstant(zone); var date = ny.toLocalDate()
        if (!isSession(date) || !ny.toLocalTime().isBefore(scheduledTime)) date = date.plusDays(1)
        while (!isSession(date)) date = date.plusDays(1)
        return ZonedDateTime.of(LocalDateTime.of(date, scheduledTime), zone)
    }
    fun holidays(year: Int): Set<LocalDate> = buildSet {
        add(observed(LocalDate.of(year, Month.JANUARY, 1))); add(nthWeekday(year, Month.JANUARY, DayOfWeek.MONDAY, 3)); add(nthWeekday(year, Month.FEBRUARY, DayOfWeek.MONDAY, 3)); add(easterSunday(year).minusDays(2))
        add(LocalDate.of(year, Month.MAY, 31).with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY)))
        if (year >= 2022) add(observed(LocalDate.of(year, Month.JUNE, 19)))
        add(observed(LocalDate.of(year, Month.JULY, 4))); add(nthWeekday(year, Month.SEPTEMBER, DayOfWeek.MONDAY, 1)); add(nthWeekday(year, Month.NOVEMBER, DayOfWeek.THURSDAY, 4)); add(observed(LocalDate.of(year, Month.DECEMBER, 25)))
    }
    private fun observed(date: LocalDate) = when (date.dayOfWeek) { DayOfWeek.SATURDAY -> date.minusDays(1); DayOfWeek.SUNDAY -> date.plusDays(1); else -> date }
    private fun nthWeekday(year: Int, month: Month, day: DayOfWeek, nth: Int) = LocalDate.of(year, month, 1).with(TemporalAdjusters.dayOfWeekInMonth(nth, day))
    internal fun easterSunday(year: Int): LocalDate {
        val a=year%19; val b=year/100; val c=year%100; val d=b/4; val e=b%4; val f=(b+8)/25; val g=(b-f+1)/3; val h=(19*a+b-d-g+15)%30; val i=c/4; val k=c%4; val l=(32+2*e+2*i-h-k)%7; val m=(a+11*h+22*l)/451; val month=(h+l-7*m+114)/31; val day=(h+l-7*m+114)%31+1
        return LocalDate.of(year, month, day)
    }
}
