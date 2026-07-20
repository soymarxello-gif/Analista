package com.analista.mobile.domain

import com.analista.mobile.data.OptionChainSnapshot
import com.analista.mobile.data.OptionContractSnapshot
import kotlin.math.abs

object OptionMetricsEngine {
    const val VERSION = "option-metrics-1"

    data class Assessment(
        val status: String,
        val coveragePct: Double,
        val putCallOiTotal: Double?,
        val putCallOiNearSpot: Double?,
        val callWallStrike: Double?,
        val putWallStrike: Double?,
        val callWallDistancePct: Double?,
        val putWallDistancePct: Double?,
        val oiConcentrationPct: Double?,
        val volumeToOiRatio: Double?,
        val ivSkewPutMinusCall: Double?,
        val gammaStatus: String,
        val bias: String,
        val score: Double,
        val reasons: List<String>,
        val engineVersion: String = VERSION
    )

    fun assess(chain: OptionChainSnapshot): Assessment {
        val contracts = chain.expiries.flatMap { it.contracts }
        if (contracts.isEmpty()) return emptyAssessment(chain.gammaStatus)

        val calls = contracts.filter { it.type == "CALL" }
        val puts = contracts.filter { it.type == "PUT" }
        val near = contracts.filter { it.distanceToSpotPct?.let { distance -> abs(distance) <= 10.0 } == true }
        val nearCalls = near.filter { it.type == "CALL" }
        val nearPuts = near.filter { it.type == "PUT" }
        val totalCallOi = calls.sumOf { it.openInterest ?: 0L }
        val totalPutOi = puts.sumOf { it.openInterest ?: 0L }
        val nearCallOi = nearCalls.sumOf { it.openInterest ?: 0L }
        val nearPutOi = nearPuts.sumOf { it.openInterest ?: 0L }
        val totalOi = totalCallOi + totalPutOi
        val totalVolume = contracts.sumOf { it.volume ?: 0L }
        val callWall = wall(calls)
        val putWall = wall(puts)
        val topOi = listOfNotNull(callWall?.openInterest, putWall?.openInterest).maxOrNull()
        val ivCall = weightedIv(nearCalls)
        val ivPut = weightedIv(nearPuts)

        val availableFields = listOf(
            totalOi > 0L,
            nearCallOi + nearPutOi > 0L,
            callWall != null,
            putWall != null,
            totalVolume > 0L,
            ivCall != null && ivPut != null,
            chain.spot != null
        ).count { it }
        val coveragePct = availableFields / 7.0 * 100.0
        val totalRatio = ratio(totalPutOi, totalCallOi)
        val nearRatio = ratio(nearPutOi, nearCallOi)
        val concentration = if (topOi != null && totalOi > 0L) topOi.toDouble() / totalOi * 100.0 else null
        val volumeOi = if (totalOi > 0L) totalVolume.toDouble() / totalOi else null
        val skew = if (ivPut != null && ivCall != null) ivPut - ivCall else null
        val callVolume = calls.sumOf { it.volume ?: 0L }
        val putVolume = puts.sumOf { it.volume ?: 0L }
        val callVolumeShare = if (callVolume + putVolume > 0L) callVolume.toDouble() / (callVolume + putVolume) else null

        val reasons = mutableListOf<String>()
        var score = 50.0
        if (nearRatio != null) {
            when {
                nearRatio >= 1.30 -> { score -= 12.0; reasons += "near_spot_put_oi_dominant" }
                nearRatio <= 0.55 -> { score += 8.0; reasons += "near_spot_call_oi_dominant" }
                else -> reasons += "near_spot_oi_balanced"
            }
        } else reasons += "near_spot_oi_unavailable"
        if (skew != null) {
            when {
                skew >= 0.10 -> { score -= 6.0; reasons += "put_iv_skew_elevated" }
                skew <= -0.05 -> { score += 3.0; reasons += "call_iv_skew_elevated" }
            }
        }
        if (concentration != null && concentration >= 35.0) reasons += "oi_concentration_high"
        if (chain.gammaStatus == "UNKNOWN") reasons += "gamma_unknown"

        val bias = when {
            coveragePct < 40.0 -> "UNKNOWN_OPTIONS_FLOW"
            nearRatio != null && nearRatio <= 0.45 && callVolumeShare != null &&
                callVolumeShare >= 0.65 && concentration != null && concentration >= 35.0 -> "CROWDED_BULLISH"
            nearRatio != null && nearRatio >= 1.80 && putVolume > callVolume &&
                concentration != null && concentration >= 35.0 -> "CROWDED_BEARISH"
            nearRatio != null && nearRatio <= 0.75 -> "BULLISH_WITH_DATA"
            nearRatio != null && nearRatio >= 1.25 -> "BEARISH_WITH_DATA"
            else -> "NEUTRAL_WITH_DATA"
        }
        val status = when {
            coveragePct >= 80.0 -> "AVAILABLE_COMPLETE"
            coveragePct >= 40.0 -> "AVAILABLE_PARTIAL"
            else -> "EMPTY"
        }
        return Assessment(
            status = status,
            coveragePct = round2(coveragePct),
            putCallOiTotal = totalRatio?.let(::round4),
            putCallOiNearSpot = nearRatio?.let(::round4),
            callWallStrike = callWall?.strike,
            putWallStrike = putWall?.strike,
            callWallDistancePct = callWall?.distanceToSpotPct?.let(::round2),
            putWallDistancePct = putWall?.distanceToSpotPct?.let(::round2),
            oiConcentrationPct = concentration?.let(::round2),
            volumeToOiRatio = volumeOi?.let(::round4),
            ivSkewPutMinusCall = skew?.let(::round4),
            gammaStatus = chain.gammaStatus,
            bias = bias,
            score = score.coerceIn(0.0, 100.0).let(::round2),
            reasons = reasons.distinct()
        )
    }

    private fun emptyAssessment(gammaStatus: String) = Assessment(
        status = "EMPTY",
        coveragePct = 0.0,
        putCallOiTotal = null,
        putCallOiNearSpot = null,
        callWallStrike = null,
        putWallStrike = null,
        callWallDistancePct = null,
        putWallDistancePct = null,
        oiConcentrationPct = null,
        volumeToOiRatio = null,
        ivSkewPutMinusCall = null,
        gammaStatus = gammaStatus,
        bias = "UNKNOWN_OPTIONS_FLOW",
        score = 50.0,
        reasons = listOf("options_chain_empty", "options_unknown_not_neutral")
    )

    private fun wall(contracts: List<OptionContractSnapshot>): OptionContractSnapshot? =
        contracts.filter { (it.openInterest ?: 0L) > 0L }
            .maxWithOrNull(compareBy<OptionContractSnapshot> { it.openInterest ?: 0L }.thenByDescending { it.strike })

    private fun weightedIv(contracts: List<OptionContractSnapshot>): Double? {
        val rows = contracts.mapNotNull { contract ->
            val iv = contract.impliedVolatility ?: return@mapNotNull null
            val weight = (contract.openInterest ?: 0L).coerceAtLeast(1L)
            iv to weight
        }
        if (rows.isEmpty()) return null
        val totalWeight = rows.sumOf { it.second }
        return rows.sumOf { it.first * it.second } / totalWeight
    }

    private fun ratio(numerator: Long, denominator: Long): Double? =
        if (denominator > 0L) numerator.toDouble() / denominator else null

    private fun round2(value: Double) = kotlin.math.round(value * 100.0) / 100.0
    private fun round4(value: Double) = kotlin.math.round(value * 10_000.0) / 10_000.0
}
