package com.analista.mobile.domain

import java.time.DayOfWeek
import java.time.LocalDate
import java.time.LocalTime
import java.time.Month
import java.time.ZonedDateTime
import java.time.temporal.TemporalAdjusters

object NyseSessionCalendar {
    const val VERSION = "xnys-rules-2026-1"

    fun isTradingSession(date: LocalDate): Boolean {
        if (date.dayOfWeek in setOf(DayOfWeek.SATURDAY, DayOfWeek.SUNDAY)) return false
        val holidays = ((date.year - 1)..(date.year + 1)).flatMap(::holidays).toSet()
        return date !in holidays
    }

    fun isEarlyClose(date: LocalDate): Boolean {
        if (!isTradingSession(date)) return false
        val thanksgiving = nthWeekday(date.year, Month.NOVEMBER, DayOfWeek.THURSDAY, 4)
        val fridayAfterThanksgiving = thanksgiving.plusDays(1)
        val julyThird = LocalDate.of(date.year, Month.JULY, 3)
        val christmasEve = LocalDate.of(date.year, Month.DECEMBER, 24)
        return date == fridayAfterThanksgiving || date == julyThird || date == christmasEve
    }

    fun closeTimeEt(date: LocalDate): LocalTime = if (isEarlyClose(date)) LocalTime.of(13, 0) else LocalTime.of(16, 0)

    fun previousTradingSession(date: LocalDate): LocalDate {
        var cursor = date.minusDays(1)
        while (!isTradingSession(cursor)) cursor = cursor.minusDays(1)
        return cursor
    }

    fun latestCompletedSession(nowEt: ZonedDateTime): LocalDate {
        val date = nowEt.toLocalDate()
        if (isTradingSession(date) && nowEt.toLocalTime() >= closeTimeEt(date).plusMinutes(15)) return date
        return previousTradingSession(date)
    }

    fun sessionsBetween(startExclusive: LocalDate, endInclusive: LocalDate): Int {
        if (!endInclusive.isAfter(startExclusive)) return 0
        var cursor = startExclusive.plusDays(1)
        var count = 0
        while (!cursor.isAfter(endInclusive)) {
            if (isTradingSession(cursor)) count += 1
            cursor = cursor.plusDays(1)
        }
        return count
    }

    internal fun holidays(year: Int): Set<LocalDate> = buildSet {
        add(observed(LocalDate.of(year, Month.JANUARY, 1)))
        add(nthWeekday(year, Month.JANUARY, DayOfWeek.MONDAY, 3))
        add(nthWeekday(year, Month.FEBRUARY, DayOfWeek.MONDAY, 3))
        add(easterSunday(year).minusDays(2))
        add(LocalDate.of(year, Month.MAY, 1).with(TemporalAdjusters.lastInMonth(DayOfWeek.MONDAY)))
        add(observed(LocalDate.of(year, Month.JUNE, 19)))
        add(observed(LocalDate.of(year, Month.JULY, 4)))
        add(nthWeekday(year, Month.SEPTEMBER, DayOfWeek.MONDAY, 1))
        add(nthWeekday(year, Month.NOVEMBER, DayOfWeek.THURSDAY, 4))
        add(observed(LocalDate.of(year, Month.DECEMBER, 25)))
    }

    private fun observed(date: LocalDate): LocalDate = when (date.dayOfWeek) {
        DayOfWeek.SATURDAY -> date.minusDays(1)
        DayOfWeek.SUNDAY -> date.plusDays(1)
        else -> date
    }

    private fun nthWeekday(year: Int, month: Month, day: DayOfWeek, ordinal: Int): LocalDate =
        LocalDate.of(year, month, 1).with(TemporalAdjusters.dayOfWeekInMonth(ordinal, day))

    private fun easterSunday(year: Int): LocalDate {
        val a = year % 19
        val b = year / 100
        val c = year % 100
        val d = b / 4
        val e = b % 4
        val f = (b + 8) / 25
        val g = (b - f + 1) / 3
        val h = (19 * a + b - d - g + 15) % 30
        val i = c / 4
        val k = c % 4
        val l = (32 + 2 * e + 2 * i - h - k) % 7
        val m = (a + 11 * h + 22 * l) / 451
        val month = (h + l - 7 * m + 114) / 31
        val day = (h + l - 7 * m + 114) % 31 + 1
        return LocalDate.of(year, month, day)
    }
}