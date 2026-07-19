package com.analista.mobile.domain

import com.analista.mobile.data.PriceBar

object RelativeStrengthEngine {
    data class Result(
        val rs20Pct: Double,
        val rs60Pct: Double,
        val score: Double,
        val status: String
    )

    fun compare(asset: List<PriceBar>, benchmark: List<PriceBar>): Result {
        require(asset.size >= 61 && benchmark.size >= 61)
        val aligned = align(asset, benchmark)
        require(aligned.size >= 61)
        val assetCloses = aligned.map { it.first.close }
        val benchmarkCloses = aligned.map { it.second.close }
        val rs20 = relativeReturn(assetCloses, benchmarkCloses, 20)
        val rs60 = relativeReturn(assetCloses, benchmarkCloses, 60)
        val score = (50.0 + rs20 * 2.0 + rs60).coerceIn(0.0, 100.0)
        val status = when {
            rs20 > 3.0 && rs60 > 5.0 -> "STRONG"
            rs20 >= 0.0 && rs60 >= 0.0 -> "POSITIVE"
            rs20 < -3.0 && rs60 < -5.0 -> "WEAK"
            else -> "MIXED"
        }
        return Result(rs20, rs60, score, status)
    }

    private fun align(asset: List<PriceBar>, benchmark: List<PriceBar>): List<Pair<PriceBar, PriceBar>> {
        val benchByTs = benchmark.associateBy { it.epochSeconds }
        return asset.mapNotNull { bar -> benchByTs[bar.epochSeconds]?.let { bar to it } }
    }

    private fun relativeReturn(asset: List<Double>, benchmark: List<Double>, period: Int): Double {
        val assetReturn = asset.last() / asset[asset.lastIndex - period] - 1.0
        val benchmarkReturn = benchmark.last() / benchmark[benchmark.lastIndex - period] - 1.0
        return (assetReturn - benchmarkReturn) * 100.0
    }
}
