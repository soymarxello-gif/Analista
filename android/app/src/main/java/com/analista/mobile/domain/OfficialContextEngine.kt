package com.analista.mobile.domain

import com.analista.mobile.data.CboeMarketStatisticsClient
import com.analista.mobile.data.CftcCotClient
import com.analista.mobile.data.FredClient
import kotlin.math.abs

object OfficialContextEngine {
    const val VERSION = "official-context-engine-1"

    data class MacroAssessment(
        val scoreAdjustment: Double,
        val liquidityRegime: String,
        val inflationRegime: String,
        val laborRegime: String,
        val ratesRegime: String,
        val coveragePct: Double,
        val reasons: List<String>
    )

    data class InstitutionalAssessment(
        val futuresScore: Double?,
        val futuresStatus: String,
        val marketOptionsRegime: String,
        val marketOptionsAdjustment: Double,
        val reasons: List<String>
    )

    data class Assessment(
        val macro: MacroAssessment,
        val institutional: InstitutionalAssessment,
        val engineVersion: String = VERSION
    )

    fun assess(
        fred: Map<String, FredClient.Series>,
        cboe: CboeMarketStatisticsClient.Ratios?,
        cftc: List<CftcCotClient.Positioning>
    ): Assessment = Assessment(
        macro = assessMacro(fred),
        institutional = assessInstitutional(cboe, cftc)
    )

    fun assessMacro(fred: Map<String, FredClient.Series>): MacroAssessment {
        val normalized = fred.mapKeys { it.key.trim().uppercase() }
        val required = listOf("DGS10", "DGS30", "T10Y2Y", "WALCL", "RRPONTSYD", "M2SL", "CPIAUCSL", "UNRATE")
        val covered = required.count { normalized[it]?.observations?.size?.let { size -> size >= 2 } == true }
        val coveragePct = covered.toDouble() / required.size * 100.0
        val reasons = mutableListOf<String>()
        var adjustment = 0.0

        val tenYearChange = delta(normalized["DGS10"], 20)
        val thirtyYearChange = delta(normalized["DGS30"], 20)
        val curve = latest(normalized["T10Y2Y"])
        val ratesRegime = when {
            tenYearChange == null && thirtyYearChange == null -> "UNKNOWN"
            listOfNotNull(tenYearChange, thirtyYearChange).average() >= 0.25 -> "RISING"
            listOfNotNull(tenYearChange, thirtyYearChange).average() <= -0.25 -> "FALLING"
            else -> "STABLE_MIXED"
        }
        when (ratesRegime) {
            "RISING" -> { adjustment -= 3.0; reasons += "fred_rates_rising" }
            "FALLING" -> { adjustment += 2.0; reasons += "fred_rates_falling" }
        }
        if (curve != null && curve < 0.0) {
            adjustment -= 2.0
            reasons += "fred_curve_inverted"
        }

        val walcl = pctChange(normalized["WALCL"], 13)
        val m2 = pctChange(normalized["M2SL"], 6)
        val reverseRepo = pctChange(normalized["RRPONTSYD"], 20)
        val expansionVotes = listOf(walcl?.let { it > 0.0 }, m2?.let { it > 0.0 }, reverseRepo?.let { it < 0.0 }).count { it == true }
        val contractionVotes = listOf(walcl?.let { it < 0.0 }, m2?.let { it < 0.0 }, reverseRepo?.let { it > 0.0 }).count { it == true }
        val liquidityRegime = when {
            expansionVotes >= 2 -> "EXPANDING"
            contractionVotes >= 2 -> "CONTRACTING"
            expansionVotes + contractionVotes == 0 -> "UNKNOWN"
            else -> "MIXED"
        }
        when (liquidityRegime) {
            "EXPANDING" -> { adjustment += 4.0; reasons += "fred_liquidity_expanding" }
            "CONTRACTING" -> { adjustment -= 4.0; reasons += "fred_liquidity_contracting" }
            "UNKNOWN" -> reasons += "fred_liquidity_unknown"
        }

        val inflationYoy = pctChange(normalized["CPIAUCSL"], 12)
        val inflationRegime = when {
            inflationYoy == null -> "UNKNOWN"
            inflationYoy >= 4.0 -> "HIGH"
            inflationYoy >= 3.0 -> "ELEVATED"
            inflationYoy <= 2.5 -> "MODERATE"
            else -> "MIXED"
        }
        when (inflationRegime) {
            "HIGH" -> { adjustment -= 5.0; reasons += "fred_inflation_high" }
            "ELEVATED" -> { adjustment -= 2.0; reasons += "fred_inflation_elevated" }
            "MODERATE" -> { adjustment += 1.0; reasons += "fred_inflation_moderate" }
        }

        val unemploymentChange = delta(normalized["UNRATE"], 3)
        val laborRegime = when {
            unemploymentChange == null -> "UNKNOWN"
            unemploymentChange >= 0.30 -> "WEAKENING"
            unemploymentChange <= -0.20 -> "IMPROVING"
            else -> "STABLE"
        }
        when (laborRegime) {
            "WEAKENING" -> { adjustment -= 3.0; reasons += "fred_labor_weakening" }
            "IMPROVING" -> { adjustment += 1.0; reasons += "fred_labor_improving" }
        }
        if (coveragePct < 50.0) reasons += "fred_macro_coverage_low"

        return MacroAssessment(
            scoreAdjustment = round2(adjustment.coerceIn(-12.0, 10.0)),
            liquidityRegime = liquidityRegime,
            inflationRegime = inflationRegime,
            laborRegime = laborRegime,
            ratesRegime = ratesRegime,
            coveragePct = round2(coveragePct),
            reasons = reasons.distinct()
        )
    }

    fun assessInstitutional(
        cboe: CboeMarketStatisticsClient.Ratios?,
        cftc: List<CftcCotClient.Positioning>
    ): InstitutionalAssessment {
        val reasons = mutableListOf<String>()
        val marketOptionsRegime = when {
            cboe == null || cboe.coverageCount == 0 -> "UNKNOWN"
            cboe.equityPutCall?.let { it <= 0.55 } == true || cboe.totalPutCall?.let { it <= 0.70 } == true -> "CROWDED_BULLISH"
            cboe.equityPutCall?.let { it >= 1.05 } == true || cboe.totalPutCall?.let { it >= 1.20 } == true -> "CROWDED_BEARISH"
            else -> "NEUTRAL_WITH_DATA"
        }
        val marketOptionsAdjustment = when (marketOptionsRegime) {
            "CROWDED_BULLISH" -> -5.0
            "CROWDED_BEARISH" -> 2.0
            else -> 0.0
        }
        when (marketOptionsRegime) {
            "CROWDED_BULLISH" -> reasons += "cboe_market_consensus_crowded_bullish"
            "CROWDED_BEARISH" -> reasons += "cboe_market_consensus_crowded_bearish"
            "UNKNOWN" -> reasons += "cboe_market_context_unknown"
        }

        val equityIndexRows = cftc
            .filter { row -> isEquityIndexMarket(row.market) }
            .groupBy { it.market.trim().uppercase() }
            .mapNotNull { (_, rows) -> rows.maxByOrNull { it.reportDate } }
        val balances = equityIndexRows.mapNotNull { row ->
            val asset = balance(row.assetManagerLong, row.assetManagerShort)
            val leveraged = balance(row.leveragedFundsLong, row.leveragedFundsShort)
            when {
                asset != null && leveraged != null -> asset * 0.70 + leveraged * 0.30
                asset != null -> asset
                else -> leveraged
            }
        }
        val futuresScore = balances.takeIf { it.isNotEmpty() }
            ?.average()
            ?.let { (50.0 + it * 35.0).coerceIn(0.0, 100.0) }
            ?.let(::round2)
        val futuresStatus = when {
            balances.size >= 3 -> "COMPLETE"
            balances.isNotEmpty() -> "PARTIAL"
            else -> "UNKNOWN"
        }
        when {
            futuresScore == null -> reasons += "cftc_equity_index_positioning_unknown"
            futuresScore >= 60.0 -> reasons += "cftc_equity_index_net_long"
            futuresScore <= 40.0 -> reasons += "cftc_equity_index_net_short"
            else -> reasons += "cftc_equity_index_positioning_balanced"
        }

        return InstitutionalAssessment(
            futuresScore = futuresScore,
            futuresStatus = futuresStatus,
            marketOptionsRegime = marketOptionsRegime,
            marketOptionsAdjustment = marketOptionsAdjustment,
            reasons = reasons.distinct()
        )
    }

    private fun latest(series: FredClient.Series?): Double? = series?.observations?.lastOrNull()?.value

    private fun delta(series: FredClient.Series?, periods: Int): Double? {
        val values = series?.observations.orEmpty()
        if (values.size < 2) return null
        val priorIndex = (values.lastIndex - periods).coerceAtLeast(0)
        return values.last().value - values[priorIndex].value
    }

    private fun pctChange(series: FredClient.Series?, periods: Int): Double? {
        val values = series?.observations.orEmpty()
        if (values.size < 2) return null
        val priorIndex = (values.lastIndex - periods).coerceAtLeast(0)
        val prior = values[priorIndex].value
        if (abs(prior) < 0.000001) return null
        return (values.last().value / prior - 1.0) * 100.0
    }

    private fun isEquityIndexMarket(value: String): Boolean {
        val normalized = value.uppercase()
        return listOf("S&P 500", "NASDAQ", "RUSSELL", "DJIA", "DOW JONES", "E-MINI S&P").any(normalized::contains)
    }

    private fun balance(long: Long?, short: Long?): Double? {
        if (long == null || short == null) return null
        val gross = abs(long.toDouble()) + abs(short.toDouble())
        return if (gross > 0.0) (long - short) / gross else null
    }

    private fun round2(value: Double) = kotlin.math.round(value * 100.0) / 100.0
}
