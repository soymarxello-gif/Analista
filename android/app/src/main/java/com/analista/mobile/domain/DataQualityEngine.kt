package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar
import java.time.DayOfWeek
import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime

object DataQualityEngine {
    const val MIN_AVERAGE_DOLLAR_VOLUME = 20_000_000.0

    data class Assessment(
        val status: String,
        val score: Double,
        val sessionsOld: Int,
        val averageDollarVolume20: Double,
        val zeroVolumeRatio60: Double,
        val reasons: List<String>,
        val executionAllowed: Boolean
    )

    fun assess(
        bars: List<PriceBar>,
        cacheHit: Boolean,
        nowMillis: Long = System.currentTimeMillis()
    ): Assessment {
        require(bars.isNotEmpty())
        val zone = ZoneId.of("America/New_York")
        val latestDate = Instant.ofEpochSecond(bars.last().epochSeconds).atZone(zone).toLocalDate()
        val expectedDate = latestCompletedSession(Instant.ofEpochMilli(nowMillis).atZone(zone))
        val sessionsOld = businessDaysBetween(latestDate, expectedDate)
        val recent = bars.takeLast(20)
        val averageDollarVolume = recent.map { it.close * it.volume }.average()
        val last60 = bars.takeLast(60)
        val zeroRatio = last60.count { it.volume <= 0L }.toDouble() / last60.size.coerceAtLeast(1)
        val reasons = mutableListOf<String>()
        var score = 100.0

        if (sessionsOld == 1) { score -= 35.0; reasons += "missing_latest_session" }
        if (sessionsOld > 1) { score -= 70.0; reasons += "stale_multiple_sessions" }
        if (cacheHit) { score -= 15.0; reasons += "cache_used" }
        if (averageDollarVolume < MIN_AVERAGE_DOLLAR_VOLUME) { score -= 35.0; reasons += "dollar_volume_below_min" }
        if (zeroRatio > 0.05) { score -= 30.0; reasons += "excess_zero_volume_bars" }

        score = score.coerceIn(0.0, 100.0)
        val status = when {
            sessionsOld > 1 -> "UNUSABLE"
            sessionsOld == 1 || averageDollarVolume < MIN_AVERAGE_DOLLAR_VOLUME || zeroRatio > 0.05 -> "LOW"
            cacheHit -> "MEDIUM"
            else -> "HIGH"
        }
        return Assessment(
            status = status,
            score = score,
            sessionsOld = sessionsOld,
            averageDollarVolume20 = averageDollarVolume,
            zeroVolumeRatio60 = zeroRatio,
            reasons = reasons,
            executionAllowed = status in setOf("HIGH", "MEDIUM") && sessionsOld == 0
        )
    }

    internal fun latestCompletedSession(nowEt: ZonedDateTime): LocalDate {
        var date = nowEt.toLocalDate()
        val afterClose = nowEt.toLocalTime() >= LocalTime.of(16, 15)
        if (date.dayOfWeek.value <= 5 && afterClose) return date
        date = date.minusDays(1)
        while (date.dayOfWeek in setOf(DayOfWeek.SATURDAY, DayOfWeek.SUNDAY)) date = date.minusDays(1)
        return date
    }

    internal fun businessDaysBetween(start: LocalDate, end: LocalDate): Int {
        if (!end.isAfter(start)) return 0
        var date = start.plusDays(1)
        var count = 0
        while (!date.isAfter(end)) {
            if (date.dayOfWeek.value <= 5) count += 1
            date = date.plusDays(1)
        }
        return count
    }
}
