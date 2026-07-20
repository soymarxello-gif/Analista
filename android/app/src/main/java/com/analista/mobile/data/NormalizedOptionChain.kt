package com.analista.mobile.data

import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.ConcurrentHashMap
import kotlin.math.abs

/** Normalized, provider-neutral options snapshot. Missing greeks remain null. */
data class OptionContractSnapshot(
    val expiryEpochSeconds: Long,
    val strike: Double,
    val type: String,
    val bid: Double?,
    val ask: Double?,
    val volume: Long?,
    val openInterest: Long?,
    val impliedVolatility: Double?,
    val delta: Double?,
    val gamma: Double?,
    val distanceToSpotPct: Double?,
    val lastTradeEpochSeconds: Long?
)

data class OptionExpirySnapshot(
    val expiryEpochSeconds: Long,
    val contracts: List<OptionContractSnapshot>
)

data class OptionChainSnapshot(
    val ticker: String,
    val spot: Double?,
    val expiries: List<OptionExpirySnapshot>,
    val availableExpiries: List<Long>,
    val capturedAtUtc: Long,
    val provider: String,
    val providerHost: String,
    val gammaStatus: String
) {
    fun toLegacyMetrics(): OptionsMetrics {
        val contracts = expiries.flatMap { it.contracts }
        val calls = contracts.filter { it.type == "CALL" }
        val puts = contracts.filter { it.type == "PUT" }
        val callOi = calls.sumOf { it.openInterest ?: 0L }
        val putOi = puts.sumOf { it.openInterest ?: 0L }
        val near = contracts.filter { distance -> distance.distanceToSpotPct?.let { abs(it) <= 10.0 } == true }
        val nearCalls = near.filter { it.type == "CALL" }.sumOf { it.openInterest ?: 0L }
        val nearPuts = near.filter { it.type == "PUT" }.sumOf { it.openInterest ?: 0L }
        return OptionsMetrics(
            putCallOi = if (callOi > 0L) putOi.toDouble() / callOi else null,
            nearCallOi = nearCalls.takeIf { it > 0L },
            nearPutOi = nearPuts.takeIf { it > 0L },
            expiry = expiries.minOfOrNull { it.expiryEpochSeconds }
        )
    }
}

object OptionChainRegistry {
    private val snapshots = ConcurrentHashMap<String, OptionChainSnapshot>()

    fun record(snapshot: OptionChainSnapshot) {
        snapshots[snapshot.ticker.trim().uppercase().replace(".", "-")] = snapshot
    }

    fun get(ticker: String): OptionChainSnapshot? = snapshots[ticker.trim().uppercase().replace(".", "-")]
    fun clear() = snapshots.clear()
}

object YahooOptionChainParser {
    const val VERSION = "yahoo-option-chain-1"

    fun parse(
        json: String,
        ticker: String,
        capturedAtUtc: Long = System.currentTimeMillis()
    ): OptionChainSnapshot {
        val result = JSONObject(json)
            .optJSONObject("optionChain")
            ?.optJSONArray("result")
            ?.optJSONObject(0)
            ?: throw IOException("No options for $ticker")
        val quote = result.optJSONObject("quote") ?: JSONObject()
        val spot = positiveDouble(quote, "regularMarketPrice")
            ?: positiveDouble(quote, "preMarketPrice")
        val availableExpiries = result.optJSONArray("expirationDates").longValues()
        val optionRows = result.optJSONArray("options")
        val expiries = buildList {
            if (optionRows != null) {
                for (index in 0 until optionRows.length()) {
                    val row = optionRows.optJSONObject(index) ?: continue
                    val expiry = row.optLong("expirationDate", 0L)
                    if (expiry <= 0L) continue
                    val contracts = parseContracts(row.optJSONArray("calls"), "CALL", expiry, spot) +
                        parseContracts(row.optJSONArray("puts"), "PUT", expiry, spot)
                    add(OptionExpirySnapshot(expiry, contracts.sortedWith(compareBy({ it.strike }, { it.type }))))
                }
            }
        }.distinctBy { it.expiryEpochSeconds }.sortedBy { it.expiryEpochSeconds }
        val allContracts = expiries.flatMap { it.contracts }
        val gammaStatus = when {
            allContracts.isEmpty() -> "UNKNOWN"
            allContracts.any { it.gamma != null } -> "AVAILABLE"
            else -> "UNKNOWN"
        }
        return OptionChainSnapshot(
            ticker = ticker.trim().uppercase().replace(".", "-"),
            spot = spot,
            expiries = expiries,
            availableExpiries = availableExpiries.distinct().sorted(),
            capturedAtUtc = capturedAtUtc,
            provider = "YAHOO",
            providerHost = "query2.finance.yahoo.com",
            gammaStatus = gammaStatus
        )
    }

    private fun parseContracts(
        array: JSONArray?,
        type: String,
        expiry: Long,
        spot: Double?
    ): List<OptionContractSnapshot> {
        if (array == null) return emptyList()
        return buildList {
            for (index in 0 until array.length()) {
                val row = array.optJSONObject(index) ?: continue
                val strike = positiveDouble(row, "strike") ?: continue
                add(
                    OptionContractSnapshot(
                        expiryEpochSeconds = expiry,
                        strike = strike,
                        type = type,
                        bid = nonNegativeDouble(row, "bid"),
                        ask = nonNegativeDouble(row, "ask"),
                        volume = nonNegativeLong(row, "volume"),
                        openInterest = nonNegativeLong(row, "openInterest"),
                        impliedVolatility = nonNegativeDouble(row, "impliedVolatility"),
                        delta = finiteDouble(row, "delta"),
                        gamma = nonNegativeDouble(row, "gamma"),
                        distanceToSpotPct = spot?.takeIf { it > 0.0 }?.let { (strike / it - 1.0) * 100.0 },
                        lastTradeEpochSeconds = positiveLong(row, "lastTradeDate")
                    )
                )
            }
        }
    }

    private fun JSONArray?.longValues(): List<Long> {
        if (this == null) return emptyList()
        return (0 until length()).mapNotNull { optLong(it, 0L).takeIf { value -> value > 0L } }
    }

    private fun positiveDouble(parent: JSONObject, key: String): Double? =
        finiteDouble(parent, key)?.takeIf { it > 0.0 }

    private fun nonNegativeDouble(parent: JSONObject, key: String): Double? =
        finiteDouble(parent, key)?.takeIf { it >= 0.0 }

    private fun finiteDouble(parent: JSONObject, key: String): Double? =
        if (parent.has(key) && !parent.isNull(key)) parent.optDouble(key).takeIf { it.isFinite() } else null

    private fun positiveLong(parent: JSONObject, key: String): Long? =
        if (parent.has(key) && !parent.isNull(key)) parent.optLong(key).takeIf { it > 0L } else null

    private fun nonNegativeLong(parent: JSONObject, key: String): Long? =
        if (parent.has(key) && !parent.isNull(key)) parent.optLong(key).takeIf { it >= 0L } else null
}
