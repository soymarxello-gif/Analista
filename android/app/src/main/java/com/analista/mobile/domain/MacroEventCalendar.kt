package com.analista.mobile.domain

import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime
import kotlin.math.abs

object MacroEventCalendar {
    const val VERSION = "us-macro-events-2026-07-08"
    const val FED_SOURCE = "FED_FOMC_CALENDAR"
    const val BLS_SOURCE = "BLS_2026_RELEASE_CALENDAR"
    private val zone = ZoneId.of("America/New_York")

    data class Event(
        val type: String,
        val occursAtEt: LocalDateTime,
        val source: String,
        val coverage: String = "OFFICIAL"
    )

    data class Assessment(
        val risk: String,
        val scheduleCoverage: String,
        val nearestEventType: String?,
        val nearestEventAtUtc: Long?,
        val hoursToNearestEvent: Double?,
        val reasons: List<String>,
        val calendarVersion: String = VERSION
    )

    fun assess(timestampUtc: Long): Assessment {
        require(timestampUtc > 0L)
        val assessment = Instant.ofEpochMilli(timestampUtc).atZone(zone)
        val year = assessment.year
        val coverage = when (year) {
            2026 -> "COMPLETE"
            2027 -> "PARTIAL_FOMC_ONLY"
            else -> "UNKNOWN"
        }
        val eligibleEvents = events.filter { event ->
            val eventYear = event.occursAtEt.year
            eventYear == year || eventYear == year + 1 || eventYear == year - 1
        }
        val nearest = eligibleEvents.minByOrNull { event ->
            abs(Duration.between(assessment, event.occursAtEt.atZone(zone)).toMinutes())
        }
        if (nearest == null) {
            return Assessment("UNKNOWN", coverage, null, null, null, listOf("macro_event_schedule_unavailable"))
        }
        val eventTime = nearest.occursAtEt.atZone(zone)
        val minutes = Duration.between(assessment, eventTime).toMinutes()
        val hours = minutes / 60.0
        val risk = when {
            minutes in -120..1_440 -> "IMMINENT"
            minutes in 1_441..4_320 -> "NEAR"
            coverage == "COMPLETE" -> "CLEAR"
            else -> "UNKNOWN"
        }
        val reasons = mutableListOf<String>()
        when (risk) {
            "IMMINENT" -> reasons += "macro_event_imminent_${nearest.type.lowercase()}"
            "NEAR" -> reasons += "macro_event_near_${nearest.type.lowercase()}"
            "CLEAR" -> reasons += "macro_event_window_clear"
            else -> reasons += "macro_event_schedule_partial"
        }
        if (coverage == "PARTIAL_FOMC_ONLY") reasons += "bls_schedule_not_published_for_year"
        return Assessment(
            risk = risk,
            scheduleCoverage = coverage,
            nearestEventType = nearest.type,
            nearestEventAtUtc = eventTime.toInstant().toEpochMilli(),
            hoursToNearestEvent = round2(hours),
            reasons = reasons.distinct()
        )
    }

    fun eventsForYear(year: Int): List<Event> = events.filter { it.occursAtEt.year == year }

    private val events: List<Event> = buildList {
        addBls("EMPLOYMENT_SITUATION", listOf(
            "2026-01-09", "2026-02-11", "2026-03-06", "2026-04-03",
            "2026-05-08", "2026-06-05", "2026-07-02", "2026-08-07",
            "2026-09-04", "2026-10-02", "2026-11-06", "2026-12-04"
        ))
        addBls("CPI", listOf(
            "2026-01-13", "2026-02-13", "2026-03-11", "2026-04-10",
            "2026-05-12", "2026-06-10", "2026-07-14", "2026-08-12",
            "2026-09-11", "2026-10-14", "2026-11-10", "2026-12-10"
        ))
        addFomc(listOf(
            "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
            "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
            "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09",
            "2027-07-28", "2027-09-15", "2027-10-27", "2027-12-08"
        ))
    }.sortedBy { it.occursAtEt }

    private fun MutableList<Event>.addBls(type: String, dates: List<String>) {
        dates.forEach { date ->
            add(Event(type, LocalDateTime.of(LocalDate.parse(date), LocalTime.of(8, 30)), BLS_SOURCE))
        }
    }

    private fun MutableList<Event>.addFomc(dates: List<String>) {
        dates.forEach { date ->
            add(Event("FOMC_DECISION", LocalDateTime.of(LocalDate.parse(date), LocalTime.of(14, 0)), FED_SOURCE))
        }
    }

    private fun round2(value: Double) = kotlin.math.round(value * 100.0) / 100.0
}
