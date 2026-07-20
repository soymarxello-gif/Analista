package com.analista.mobile.domain

import java.time.DayOfWeek
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZonedDateTime

object NyseSessionCalendar {
    const val VERSION = "xnys-2025-2028.1"
    val zoneId = java.time.ZoneId.of("America/New_York")

    data class Session(
        val date: LocalDate,
        val status: String,
        val openTimeEt: LocalTime?,
        val closeTimeEt: LocalTime?,
        val earlyClose: Boolean,
        val calendarVersion: String = VERSION
    ) {
        val isTradingSession: Boolean get() = status == "OPEN"
    }

    private val holidays = setOf(
        // 2025
        LocalDate.of(2025, 1, 1), LocalDate.of(2025, 1, 20), LocalDate.of(2025, 2, 17),
        LocalDate.of(2025, 4, 18), LocalDate.of(2025, 5, 26), LocalDate.of(2025, 6, 19),
        LocalDate.of(2025, 7, 4), LocalDate.of(2025, 9, 1), LocalDate.of(2025, 11, 27),
        LocalDate.of(2025, 12, 25),
        // 2026
        LocalDate.of(2026, 1, 1), LocalDate.of(2026, 1, 19), LocalDate.of(2026, 2, 16),
        LocalDate.of(2026, 4, 3), LocalDate.of(2026, 5, 25), LocalDate.of(2026, 6, 19),
        LocalDate.of(2026, 7, 3), LocalDate.of(2026, 9, 7), LocalDate.of(2026, 11, 26),
        LocalDate.of(2026, 12, 25),
        // 2027
        LocalDate.of(2027, 1, 1), LocalDate.of(2027, 1, 18), LocalDate.of(2027, 2, 15),
        LocalDate.of(2027, 3, 26), LocalDate.of(2027, 5, 31), LocalDate.of(2027, 6, 18),
        LocalDate.of(2027, 7, 5), LocalDate.of(2027, 9, 6), LocalDate.of(2027, 11, 25),
        LocalDate.of(2027, 12, 24),
        // 2028
        LocalDate.of(2028, 1, 17), LocalDate.of(2028, 2, 21), LocalDate.of(2028, 4, 14),
        LocalDate.of(2028, 5, 29), LocalDate.of(2028, 6, 19), LocalDate.of(2028, 7, 4),
        LocalDate.of(2028, 9, 4), LocalDate.of(2028, 11, 23), LocalDate.of(2028, 12, 25)
    )

    private val earlyCloses = setOf(
        LocalDate.of(2025, 7, 3), LocalDate.of(2025, 11, 28), LocalDate.of(2025, 12, 24),
        LocalDate.of(2026, 11, 27), LocalDate.of(2026, 12, 24),
        LocalDate.of(2027, 11, 26),
        LocalDate.of(2028, 7, 3), LocalDate.of(2028, 11, 24)
    )

    fun session(date: LocalDate): Session {
        if (date.dayOfWeek in setOf(DayOfWeek.SATURDAY, DayOfWeek.SUNDAY)) {
            return Session(date, "CLOSED_WEEKEND", null, null, false)
        }
        if (date in holidays) return Session(date, "CLOSED_HOLIDAY", null, null, false)
        val early = date in earlyCloses
        return Session(
            date = date,
            status = "OPEN",
            openTimeEt = LocalTime.of(9, 30),
            closeTimeEt = if (early) LocalTime.of(13, 0) else LocalTime.of(16, 0),
            earlyClose = early
        )
    }

    fun latestCompletedSession(nowEt: ZonedDateTime): LocalDate {
        require(nowEt.zone == zoneId || nowEt.withZoneSameInstant(zoneId).zone == zoneId)
        val normalized = nowEt.withZoneSameInstant(zoneId)
        val today = session(normalized.toLocalDate())
        val close = today.closeTimeEt
        if (today.isTradingSession && close != null && normalized.toLocalTime() >= close.plusMinutes(15)) {
            return today.date
        }
        return previousTradingSession(today.date)
    }

    fun previousTradingSession(beforeOrOn: LocalDate): LocalDate {
        var cursor = beforeOrOn.minusDays(1)
        while (!session(cursor).isTradingSession) cursor = cursor.minusDays(1)
        return cursor
    }

    fun nextTradingSession(afterOrOn: LocalDate): LocalDate {
        var cursor = afterOrOn
        while (!session(cursor).isTradingSession) cursor = cursor.plusDays(1)
        return cursor
    }

    fun sessionsBetween(startExclusive: LocalDate, endInclusive: LocalDate): Int {
        if (!endInclusive.isAfter(startExclusive)) return 0
        var cursor = startExclusive.plusDays(1)
        var count = 0
        while (!cursor.isAfter(endInclusive)) {
            if (session(cursor).isTradingSession) count += 1
            cursor = cursor.plusDays(1)
        }
        return count
    }
}
