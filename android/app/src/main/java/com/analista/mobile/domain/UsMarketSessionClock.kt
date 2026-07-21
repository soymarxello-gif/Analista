package com.analista.mobile.domain

import java.time.Instant
import java.time.LocalTime

object UsMarketSessionClock {
    const val VERSION = "us-market-session-clock-1"

    fun marketState(nowUtcMillis: Long = System.currentTimeMillis()): String {
        val nowEt = Instant.ofEpochMilli(nowUtcMillis).atZone(NyseSessionCalendar.zoneId)
        val session = NyseSessionCalendar.session(nowEt.toLocalDate())
        if (!session.isTradingSession) return "CLOSED"
        val time = nowEt.toLocalTime()
        val close = session.closeTimeEt ?: LocalTime.of(16, 0)
        return when {
            time >= LocalTime.of(4, 0) && time < LocalTime.of(9, 30) -> "PRE"
            time >= LocalTime.of(9, 30) && time < close -> "REGULAR"
            time >= close && time < LocalTime.of(20, 0) -> "POST"
            else -> "CLOSED"
        }
    }
}
