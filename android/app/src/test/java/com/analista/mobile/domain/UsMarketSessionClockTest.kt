package com.analista.mobile.domain

import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.ZonedDateTime

class UsMarketSessionClockTest {
    private fun epoch(year: Int, month: Int, day: Int, hour: Int, minute: Int): Long =
        ZonedDateTime.of(year, month, day, hour, minute, 0, 0, NyseSessionCalendar.zoneId)
            .toInstant().toEpochMilli()

    @Test
    fun derivesPremarketRegularAndClosedStates() {
        assertEquals("PRE", UsMarketSessionClock.marketState(epoch(2026, 7, 21, 9, 20)))
        assertEquals("REGULAR", UsMarketSessionClock.marketState(epoch(2026, 7, 21, 10, 0)))
        assertEquals("POST", UsMarketSessionClock.marketState(epoch(2026, 7, 21, 17, 0)))
        assertEquals("CLOSED", UsMarketSessionClock.marketState(epoch(2026, 7, 19, 10, 0)))
    }
}
