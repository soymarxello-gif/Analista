package com.analista.mobile.data

import org.json.JSONObject
import java.math.BigDecimal
import java.nio.charset.StandardCharsets
import java.security.MessageDigest

object NormalizedDatasetCodec {
    const val VERSION = "normalized-dataset-codec-1"

    fun bars(ticker: String, rows: List<PriceBar>): ByteArray = utf8(buildString {
        append("{\"ticker\":").append(q(normalizeTicker(ticker))).append(",\"bars\":[")
        rows.sortedBy { it.epochSeconds }.forEachIndexed { index, bar ->
            if (index > 0) append(',')
            append("{\"t\":").append(bar.epochSeconds)
                .append(",\"o\":").append(n(bar.open))
                .append(",\"h\":").append(n(bar.high))
                .append(",\"l\":").append(n(bar.low))
                .append(",\"c\":").append(n(bar.close))
                .append(",\"v\":").append(bar.volume).append('}')
        }
        append("]}")
    })

    fun quote(ticker: String, value: MarketQuote?): ByteArray = utf8(buildString {
        append("{\"ticker\":").append(q(normalizeTicker(ticker))).append(",\"quote\":")
        if (value == null) append("null") else {
            append("{\"bid\":").append(n(value.bid))
                .append(",\"ask\":").append(n(value.ask))
                .append(",\"regularMarketPrice\":").append(n(value.regularMarketPrice))
                .append(",\"preMarketPrice\":").append(n(value.preMarketPrice))
                .append(",\"marketCap\":").append(value.marketCap ?: "null")
                .append(",\"quoteType\":").append(qn(value.quoteType))
                .append(",\"marketState\":").append(qn(value.marketState))
                .append(",\"providerTimestampUtc\":").append(value.providerTimestampUtc ?: "null")
                .append(",\"retrievedAtUtc\":").append(value.retrievedAtUtc)
                .append(",\"provider\":").append(q(value.provider)).append('}')
        }
        append('}')
    })

    fun macro(rows: List<MarketSnapshotEntity>): ByteArray = utf8(buildString {
        append("{\"snapshots\":[")
        rows.sortedBy { it.symbol }.forEachIndexed { index, row ->
            if (index > 0) append(',')
            append("{\"symbol\":").append(q(row.symbol))
                .append(",\"label\":").append(q(row.label))
                .append(",\"close\":").append(n(row.close))
                .append(",\"changePct\":").append(n(row.changePct))
                .append(",\"capturedAtUtc\":").append(row.capturedAtUtc).append('}')
        }
        append("]}")
    })

    fun fundamentals(rows: List<FundamentalSnapshotEntity>): ByteArray = utf8(buildString {
        append("{\"fundamentals\":[")
        rows.sortedBy { it.ticker }.forEachIndexed { index, row ->
            if (index > 0) append(',')
            append("{\"ticker\":").append(q(row.ticker))
                .append(",\"revenueYoyPct\":").append(n(row.revenueYoyPct))
                .append(",\"revenueTrend\":").append(q(row.revenueTrend))
                .append(",\"epsYoyPct\":").append(n(row.epsYoyPct))
                .append(",\"epsTrend\":").append(q(row.epsTrend))
                .append(",\"grossMarginPct\":").append(n(row.grossMarginPct))
                .append(",\"grossMarginDeltaPct\":").append(n(row.grossMarginDeltaPct))
                .append(",\"operatingMarginPct\":").append(n(row.operatingMarginPct))
                .append(",\"operatingMarginDeltaPct\":").append(n(row.operatingMarginDeltaPct))
                .append(",\"netMarginPct\":").append(n(row.netMarginPct))
                .append(",\"netMarginDeltaPct\":").append(n(row.netMarginDeltaPct))
                .append(",\"debtToEquity\":").append(n(row.debtToEquity))
                .append(",\"debtToEbitda\":").append(n(row.debtToEbitda))
                .append(",\"interestCoverage\":").append(n(row.interestCoverage))
                .append(",\"freeCashFlow\":").append(n(row.freeCashFlow))
                .append(",\"priceToSales\":").append(n(row.priceToSales))
                .append(",\"sectorPriceToSalesMedian\":").append(n(row.sectorPriceToSalesMedian))
                .append(",\"earningsDateUtc\":").append(row.earningsDateUtc ?: "null")
                .append(",\"earningsSessions\":").append(row.earningsSessions ?: "null")
                .append(",\"earningsRiskStatus\":").append(q(row.earningsRiskStatus))
                .append(",\"dataAgeDays\":").append(row.dataAgeDays ?: "null")
                .append(",\"sector\":").append(qn(row.sector))
                .append(",\"coveragePct\":").append(n(row.coveragePct))
                .append(",\"status\":").append(q(row.status))
                .append(",\"fundamentalScore\":").append(n(row.fundamentalScore))
                .append(",\"reasons\":").append(q(row.reasons))
                .append(",\"engineVersion\":").append(q(row.engineVersion))
                .append(",\"capturedAtUtc\":").append(row.capturedAtUtc).append('}')
        }
        append("]}")
    })

    fun options(snapshot: OptionChainSnapshot): ByteArray = utf8(buildString {
        append("{\"ticker\":").append(q(normalizeTicker(snapshot.ticker)))
            .append(",\"spot\":").append(n(snapshot.spot))
            .append(",\"capturedAtUtc\":").append(snapshot.capturedAtUtc)
            .append(",\"provider\":").append(q(snapshot.provider))
            .append(",\"providerHost\":").append(q(snapshot.providerHost))
            .append(",\"gammaStatus\":").append(q(snapshot.gammaStatus))
            .append(",\"expiries\":[")
        snapshot.expiries.sortedBy { it.expiryEpochSeconds }.forEachIndexed { expiryIndex, expiry ->
            if (expiryIndex > 0) append(',')
            append("{\"expiry\":").append(expiry.expiryEpochSeconds).append(",\"contracts\":[")
            expiry.contracts.sortedWith(compareBy<OptionContractSnapshot> { it.strike }.thenBy { it.type })
                .forEachIndexed { contractIndex, row ->
                    if (contractIndex > 0) append(',')
                    append("{\"strike\":").append(n(row.strike))
                        .append(",\"type\":").append(q(row.type))
                        .append(",\"bid\":").append(n(row.bid))
                        .append(",\"ask\":").append(n(row.ask))
                        .append(",\"volume\":").append(row.volume ?: "null")
                        .append(",\"openInterest\":").append(row.openInterest ?: "null")
                        .append(",\"impliedVolatility\":").append(n(row.impliedVolatility))
                        .append(",\"delta\":").append(n(row.delta))
                        .append(",\"gamma\":").append(n(row.gamma))
                        .append(",\"distanceToSpotPct\":").append(n(row.distanceToSpotPct))
                        .append(",\"lastTradeEpochSeconds\":").append(row.lastTradeEpochSeconds ?: "null")
                        .append('}')
                }
            append("]}")
        }
        append("]}")
    })

    fun universe(snapshot: UniverseSnapshotEntity, members: List<UniverseMemberEntity>): ByteArray = utf8(buildString {
        append("{\"snapshotId\":").append(q(snapshot.snapshotId))
            .append(",\"effectiveDate\":").append(q(snapshot.effectiveDate))
            .append(",\"selectionRuleVersion\":").append(q(snapshot.selectionRuleVersion))
            .append(",\"mode\":").append(q(snapshot.mode))
            .append(",\"source\":").append(q(snapshot.source))
            .append(",\"status\":").append(q(snapshot.status))
            .append(",\"members\":[")
        members.sortedBy { it.ticker }.forEachIndexed { index, row ->
            if (index > 0) append(',')
            append("{\"ticker\":").append(q(row.ticker))
                .append(",\"sector\":").append(qn(row.sector))
                .append(",\"industry\":").append(qn(row.industry))
                .append(",\"instrumentType\":").append(q(row.instrumentType))
                .append(",\"adrStatus\":").append(q(row.adrStatus))
                .append(",\"price\":").append(n(row.price))
                .append(",\"marketCap\":").append(row.marketCap ?: "null")
                .append(",\"averageDollarVolume20\":").append(n(row.averageDollarVolume20))
                .append(",\"spreadPct\":").append(n(row.spreadPct))
                .append(",\"eligible\":").append(row.eligible)
                .append(",\"exclusionReasons\":").append(q(row.exclusionReasons))
                .append(",\"capturedAtUtc\":").append(row.capturedAtUtc).append('}')
        }
        append("]}")
    })

    fun sha256(payload: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(payload)
        .joinToString("") { "%02x".format(it) }

    private fun utf8(value: String) = value.toByteArray(StandardCharsets.UTF_8)
    private fun q(value: String) = JSONObject.quote(value)
    private fun qn(value: String?) = value?.let(::q) ?: "null"
    private fun n(value: Double?): String = when {
        value == null -> "null"
        !value.isFinite() -> throw IllegalArgumentException("non-finite numeric value")
        else -> BigDecimal.valueOf(value).stripTrailingZeros().toPlainString()
    }
    private fun normalizeTicker(value: String) = value.trim().uppercase().replace(".", "-")
}
