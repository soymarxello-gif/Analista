package com.analista.mobile.domain

import com.analista.mobile.data.UniverseMemberEntity
import com.analista.mobile.data.UniverseSnapshotEntity
import java.nio.charset.StandardCharsets
import java.security.MessageDigest

object UniverseSelectionEngine {
    const val VERSION = "universe-selection-1"
    const val MODE = "us_listed_common_equities"
    const val MIN_AVERAGE_DOLLAR_VOLUME = 20_000_000.0
    const val MAX_SPREAD_PCT = 1.0

    private val allowedTypes = setOf("EQUITY", "COMMON_STOCK", "ADR", "FOREIGN_ISSUER")
    private val excludedTypes = setOf(
        "ETF", "ETN", "CLOSED_END_FUND", "CEF", "PREFERRED", "PREFERRED_SHARE",
        "WARRANT", "RIGHT", "RIGHTS", "UNIT", "MUTUALFUND", "MUTUAL_FUND", "SPAC_PRE_DEAL"
    )

    data class Input(
        val ticker: String,
        val sector: String? = null,
        val industry: String? = null,
        val instrumentType: String?,
        val adrStatus: String? = null,
        val price: Double?,
        val marketCap: Long?,
        val averageDollarVolume20: Double?,
        val spreadPct: Double?,
        val capturedAtUtc: Long
    )

    data class Assessment(
        val ticker: String,
        val eligible: Boolean,
        val reasons: List<String>,
        val normalizedInstrumentType: String,
        val normalizedAdrStatus: String
    )

    data class SnapshotBundle(
        val snapshot: UniverseSnapshotEntity,
        val members: List<UniverseMemberEntity>
    )

    fun assess(input: Input): Assessment {
        val ticker = normalizeTicker(input.ticker)
        require(ticker.isNotBlank())
        require(input.capturedAtUtc > 0L)
        val type = input.instrumentType?.trim()?.uppercase()?.replace(' ', '_').orEmpty().ifBlank { "UNKNOWN" }
        val adrStatus = input.adrStatus?.trim()?.uppercase()?.replace(' ', '_').orEmpty().ifBlank { "NOT_ADR_OR_UNKNOWN" }
        val reasons = mutableListOf<String>()
        if (input.price == null || input.price < TradingPolicy.MIN_PRICE) reasons += "price_below_min"
        if (input.marketCap == null || input.marketCap < TradingPolicy.MIN_MARKET_CAP) reasons += "market_cap_below_min"
        if (input.averageDollarVolume20 == null || input.averageDollarVolume20 < MIN_AVERAGE_DOLLAR_VOLUME) {
            reasons += "dollar_volume_below_min"
        }
        if (input.spreadPct == null || input.spreadPct > MAX_SPREAD_PCT) reasons += "spread_unacceptable"
        when {
            type in excludedTypes -> reasons += "excluded_security_type"
            type !in allowedTypes -> reasons += "instrument_type_not_eligible"
        }
        if (adrStatus == "ILLIQUID_ADR") reasons += "illiquid_adr"
        return Assessment(ticker, reasons.isEmpty(), reasons.distinct(), type, adrStatus)
    }

    fun createSnapshot(
        effectiveDate: String,
        inputs: List<Input>,
        source: String,
        createdAtUtc: Long
    ): SnapshotBundle {
        require(effectiveDate.matches(Regex("\\d{4}-\\d{2}-\\d{2}")))
        require(inputs.isNotEmpty())
        require(source.isNotBlank())
        require(createdAtUtc > 0L)
        val normalized = inputs.map { it.copy(ticker = normalizeTicker(it.ticker)) }
        require(normalized.all { it.ticker.isNotBlank() })
        require(normalized.map { it.ticker }.distinct().size == normalized.size) { "duplicate universe ticker" }
        val sorted = normalized.sortedBy { it.ticker }
        val canonical = sorted.joinToString("\n") { input ->
            val assessment = assess(input)
            listOf(
                input.ticker,
                assessment.normalizedInstrumentType,
                assessment.normalizedAdrStatus,
                canonical(input.price),
                input.marketCap?.toString().orEmpty(),
                canonical(input.averageDollarVolume20),
                canonical(input.spreadPct),
                assessment.eligible.toString(),
                assessment.reasons.joinToString("|")
            ).joinToString(",")
        }
        val snapshotId = "universe-$effectiveDate-${sha256("$VERSION\n$canonical").take(16)}"
        val members = sorted.map { input ->
            val assessment = assess(input)
            UniverseMemberEntity(
                memberId = "$snapshotId-${assessment.ticker}",
                snapshotId = snapshotId,
                ticker = assessment.ticker,
                sector = input.sector?.trim()?.takeIf { it.isNotEmpty() },
                industry = input.industry?.trim()?.takeIf { it.isNotEmpty() },
                instrumentType = assessment.normalizedInstrumentType,
                adrStatus = assessment.normalizedAdrStatus,
                price = input.price,
                marketCap = input.marketCap,
                averageDollarVolume20 = input.averageDollarVolume20,
                spreadPct = input.spreadPct,
                eligible = assessment.eligible,
                exclusionReasons = assessment.reasons.joinToString("|"),
                capturedAtUtc = input.capturedAtUtc
            )
        }
        val eligibleSymbols = members.filter { it.eligible }.map { it.ticker }
        val snapshot = UniverseSnapshotEntity(
            snapshotId = snapshotId,
            effectiveDate = effectiveDate,
            selectionRuleVersion = VERSION,
            mode = MODE,
            symbols = eligibleSymbols.joinToString(","),
            symbolCount = members.size,
            eligibleCount = eligibleSymbols.size,
            source = source.trim(),
            status = if (eligibleSymbols.isEmpty()) "EMPTY" else "VALID",
            createdAtUtc = createdAtUtc
        )
        return SnapshotBundle(snapshot, members)
    }

    private fun normalizeTicker(ticker: String) = ticker.trim().uppercase().replace(".", "-")
    private fun canonical(value: Double?) = value?.let {
        java.lang.String.format(java.util.Locale.US, "%.6f", it)
    }.orEmpty()

    private fun sha256(value: String): String = MessageDigest.getInstance("SHA-256")
        .digest(value.toByteArray(StandardCharsets.UTF_8))
        .joinToString("") { "%02x".format(it) }
}
