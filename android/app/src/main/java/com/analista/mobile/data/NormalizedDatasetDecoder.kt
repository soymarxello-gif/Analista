package com.analista.mobile.data

import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException

object NormalizedDatasetDecoder {
    const val VERSION = "normalized-dataset-decoder-1"

    data class BarsDataset(val ticker: String, val bars: List<PriceBar>)
    data class QuoteDataset(val ticker: String, val quote: MarketQuote?)
    data class UniverseDataset(
        val snapshot: UniverseSnapshotEntity,
        val members: List<UniverseMemberEntity>
    )

    fun bars(payload: ByteArray): BarsDataset {
        val root = json(payload)
        val ticker = requiredString(root, "ticker")
        val array = root.optJSONArray("bars") ?: throw IOException("bars missing")
        val rows = buildList {
            for (index in 0 until array.length()) {
                val row = array.optJSONObject(index) ?: throw IOException("invalid bar at $index")
                add(
                    PriceBar(
                        epochSeconds = requiredLong(row, "t"),
                        open = requiredPositiveDouble(row, "o"),
                        high = requiredPositiveDouble(row, "h"),
                        low = requiredPositiveDouble(row, "l"),
                        close = requiredPositiveDouble(row, "c"),
                        volume = requiredNonNegativeLong(row, "v")
                    )
                )
            }
        }
        require(rows.zipWithNext().all { (first, second) -> first.epochSeconds < second.epochSeconds }) {
            "bars must be strictly chronological"
        }
        require(rows.all { it.high >= maxOf(it.open, it.close, it.low) && it.low <= minOf(it.open, it.close, it.high) }) {
            "invalid OHLC relationship"
        }
        return BarsDataset(ticker, rows)
    }

    fun quote(payload: ByteArray): QuoteDataset {
        val root = json(payload)
        val ticker = requiredString(root, "ticker")
        if (root.isNull("quote")) return QuoteDataset(ticker, null)
        val row = root.optJSONObject("quote") ?: throw IOException("quote invalid")
        val providerTimestamp = optionalLong(row, "providerTimestampUtc")
        val retrieved = requiredLong(row, "retrievedAtUtc")
        return QuoteDataset(
            ticker,
            MarketQuote(
                bid = optionalDouble(row, "bid"),
                ask = optionalDouble(row, "ask"),
                regularMarketPrice = optionalDouble(row, "regularMarketPrice"),
                preMarketPrice = optionalDouble(row, "preMarketPrice"),
                marketCap = optionalLong(row, "marketCap"),
                quoteType = optionalString(row, "quoteType"),
                marketState = optionalString(row, "marketState"),
                capturedAtUtc = providerTimestamp ?: retrieved,
                providerTimestampUtc = providerTimestamp,
                retrievedAtUtc = retrieved,
                provider = requiredString(row, "provider")
            )
        )
    }

    fun macro(payload: ByteArray, runId: String): List<MarketSnapshotEntity> {
        require(runId.isNotBlank())
        val array = json(payload).optJSONArray("snapshots") ?: throw IOException("macro snapshots missing")
        return buildList {
            for (index in 0 until array.length()) {
                val row = array.optJSONObject(index) ?: throw IOException("invalid macro snapshot at $index")
                val symbol = requiredString(row, "symbol")
                add(
                    MarketSnapshotEntity(
                        snapshotId = "$runId-$symbol",
                        runId = runId,
                        symbol = symbol,
                        label = requiredString(row, "label"),
                        close = requiredPositiveDouble(row, "close"),
                        changePct = requiredFiniteDouble(row, "changePct"),
                        capturedAtUtc = requiredLong(row, "capturedAtUtc")
                    )
                )
            }
        }.sortedBy { it.symbol }
    }

    fun fundamentals(payload: ByteArray, runId: String): List<FundamentalSnapshotEntity> {
        require(runId.isNotBlank())
        val array = json(payload).optJSONArray("fundamentals") ?: throw IOException("fundamentals missing")
        return buildList {
            for (index in 0 until array.length()) {
                val row = array.optJSONObject(index) ?: throw IOException("invalid fundamental at $index")
                val ticker = requiredString(row, "ticker")
                add(
                    FundamentalSnapshotEntity(
                        snapshotId = "$runId-$ticker",
                        runId = runId,
                        ticker = ticker,
                        revenueYoyPct = optionalDouble(row, "revenueYoyPct"),
                        revenueTrend = requiredString(row, "revenueTrend"),
                        epsYoyPct = optionalDouble(row, "epsYoyPct"),
                        epsTrend = requiredString(row, "epsTrend"),
                        grossMarginPct = optionalDouble(row, "grossMarginPct"),
                        grossMarginDeltaPct = optionalDouble(row, "grossMarginDeltaPct"),
                        operatingMarginPct = optionalDouble(row, "operatingMarginPct"),
                        operatingMarginDeltaPct = optionalDouble(row, "operatingMarginDeltaPct"),
                        netMarginPct = optionalDouble(row, "netMarginPct"),
                        netMarginDeltaPct = optionalDouble(row, "netMarginDeltaPct"),
                        debtToEquity = optionalDouble(row, "debtToEquity"),
                        debtToEbitda = optionalDouble(row, "debtToEbitda"),
                        interestCoverage = optionalDouble(row, "interestCoverage"),
                        freeCashFlow = optionalDouble(row, "freeCashFlow"),
                        priceToSales = optionalDouble(row, "priceToSales"),
                        sectorPriceToSalesMedian = optionalDouble(row, "sectorPriceToSalesMedian"),
                        earningsDateUtc = optionalLong(row, "earningsDateUtc"),
                        earningsSessions = optionalInt(row, "earningsSessions"),
                        earningsRiskStatus = requiredString(row, "earningsRiskStatus"),
                        dataAgeDays = optionalLong(row, "dataAgeDays"),
                        sector = optionalString(row, "sector"),
                        coveragePct = requiredFiniteDouble(row, "coveragePct"),
                        status = requiredString(row, "status"),
                        fundamentalScore = requiredFiniteDouble(row, "fundamentalScore"),
                        reasons = requiredString(row, "reasons"),
                        engineVersion = requiredString(row, "engineVersion"),
                        capturedAtUtc = requiredLong(row, "capturedAtUtc")
                    )
                )
            }
        }.sortedBy { it.ticker }
    }

    fun options(payload: ByteArray): OptionChainSnapshot {
        val root = json(payload)
        val ticker = requiredString(root, "ticker")
        val expiriesArray = root.optJSONArray("expiries") ?: throw IOException("option expiries missing")
        val expiries = buildList {
            for (expiryIndex in 0 until expiriesArray.length()) {
                val expiryRow = expiriesArray.optJSONObject(expiryIndex) ?: throw IOException("invalid expiry")
                val expiry = requiredLong(expiryRow, "expiry")
                val contractsArray = expiryRow.optJSONArray("contracts") ?: JSONArray()
                val contracts = buildList {
                    for (contractIndex in 0 until contractsArray.length()) {
                        val row = contractsArray.optJSONObject(contractIndex) ?: throw IOException("invalid option contract")
                        add(
                            OptionContractSnapshot(
                                expiryEpochSeconds = expiry,
                                strike = requiredPositiveDouble(row, "strike"),
                                type = requiredString(row, "type"),
                                bid = optionalDouble(row, "bid"),
                                ask = optionalDouble(row, "ask"),
                                volume = optionalLong(row, "volume"),
                                openInterest = optionalLong(row, "openInterest"),
                                impliedVolatility = optionalDouble(row, "impliedVolatility"),
                                delta = optionalDouble(row, "delta"),
                                gamma = optionalDouble(row, "gamma"),
                                distanceToSpotPct = optionalDouble(row, "distanceToSpotPct"),
                                lastTradeEpochSeconds = optionalLong(row, "lastTradeEpochSeconds")
                            )
                        )
                    }
                }.sortedWith(compareBy<OptionContractSnapshot> { it.strike }.thenBy { it.type })
                add(OptionExpirySnapshot(expiry, contracts))
            }
        }.sortedBy { it.expiryEpochSeconds }
        return OptionChainSnapshot(
            ticker = ticker,
            spot = optionalDouble(root, "spot"),
            expiries = expiries,
            availableExpiries = expiries.map { it.expiryEpochSeconds },
            capturedAtUtc = requiredLong(root, "capturedAtUtc"),
            provider = requiredString(root, "provider"),
            providerHost = requiredString(root, "providerHost"),
            gammaStatus = requiredString(root, "gammaStatus")
        )
    }

    fun universe(payload: ByteArray): UniverseDataset {
        val root = json(payload)
        val snapshotId = requiredString(root, "snapshotId")
        val memberArray = root.optJSONArray("members") ?: throw IOException("universe members missing")
        val members = buildList {
            for (index in 0 until memberArray.length()) {
                val row = memberArray.optJSONObject(index) ?: throw IOException("invalid universe member")
                val ticker = requiredString(row, "ticker")
                add(
                    UniverseMemberEntity(
                        memberId = "$snapshotId-$ticker",
                        snapshotId = snapshotId,
                        ticker = ticker,
                        sector = optionalString(row, "sector"),
                        industry = optionalString(row, "industry"),
                        instrumentType = requiredString(row, "instrumentType"),
                        adrStatus = requiredString(row, "adrStatus"),
                        price = optionalDouble(row, "price"),
                        marketCap = optionalLong(row, "marketCap"),
                        averageDollarVolume20 = optionalDouble(row, "averageDollarVolume20"),
                        spreadPct = optionalDouble(row, "spreadPct"),
                        eligible = requiredBoolean(row, "eligible"),
                        exclusionReasons = requiredString(row, "exclusionReasons"),
                        capturedAtUtc = requiredLong(row, "capturedAtUtc")
                    )
                )
            }
        }.sortedBy { it.ticker }
        val createdAtUtc = members.maxOfOrNull { it.capturedAtUtc } ?: 1L
        val symbols = members.map { it.ticker }.joinToString(",")
        return UniverseDataset(
            snapshot = UniverseSnapshotEntity(
                snapshotId = snapshotId,
                effectiveDate = requiredString(root, "effectiveDate"),
                selectionRuleVersion = requiredString(root, "selectionRuleVersion"),
                mode = requiredString(root, "mode"),
                symbols = symbols,
                symbolCount = members.size,
                eligibleCount = members.count { it.eligible },
                source = requiredString(root, "source"),
                status = requiredString(root, "status"),
                createdAtUtc = createdAtUtc
            ),
            members = members
        )
    }

    private fun json(payload: ByteArray): JSONObject = try {
        JSONObject(payload.toString(Charsets.UTF_8))
    } catch (error: Throwable) {
        throw IOException("invalid normalized dataset", error)
    }

    private fun requiredString(row: JSONObject, key: String): String =
        row.optString(key).takeIf { row.has(key) && !row.isNull(key) && it.isNotBlank() }
            ?: throw IOException("missing string: $key")

    private fun optionalString(row: JSONObject, key: String): String? =
        if (row.has(key) && !row.isNull(key)) row.optString(key).takeIf { it.isNotBlank() } else null

    private fun requiredLong(row: JSONObject, key: String): Long =
        if (row.has(key) && !row.isNull(key)) row.optLong(key) else throw IOException("missing long: $key")

    private fun optionalLong(row: JSONObject, key: String): Long? =
        if (row.has(key) && !row.isNull(key)) row.optLong(key) else null

    private fun optionalInt(row: JSONObject, key: String): Int? =
        if (row.has(key) && !row.isNull(key)) row.optInt(key) else null

    private fun requiredNonNegativeLong(row: JSONObject, key: String): Long =
        requiredLong(row, key).takeIf { it >= 0L } ?: throw IOException("negative long: $key")

    private fun requiredPositiveDouble(row: JSONObject, key: String): Double =
        requiredFiniteDouble(row, key).takeIf { it > 0.0 } ?: throw IOException("non-positive double: $key")

    private fun requiredFiniteDouble(row: JSONObject, key: String): Double =
        if (row.has(key) && !row.isNull(key)) row.optDouble(key).takeIf { it.isFinite() }
            ?: throw IOException("invalid double: $key")
        else throw IOException("missing double: $key")

    private fun optionalDouble(row: JSONObject, key: String): Double? =
        if (row.has(key) && !row.isNull(key)) row.optDouble(key).takeIf { it.isFinite() } else null

    private fun requiredBoolean(row: JSONObject, key: String): Boolean =
        if (row.has(key) && !row.isNull(key)) row.getBoolean(key) else throw IOException("missing boolean: $key")
}
