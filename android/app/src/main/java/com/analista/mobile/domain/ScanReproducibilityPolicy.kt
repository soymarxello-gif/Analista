package com.analista.mobile.domain

import com.analista.mobile.data.YahooOptionChainParser

object ScanReproducibilityPolicy {
    const val VERSION = "scan-repro-policy-5"
    const val HISTORY_PROVIDER = "YAHOO"
    const val HISTORY_HOST = "query1.finance.yahoo.com"

    data class RuntimeInput(
        val dataQualityStatus: String,
        val cacheHit: Boolean,
        val retries: Int,
        val riskPct: Double = 1.0,
        val maxPositionPct: Double = 20.0,
        val minRiskReward: Double = 2.0,
        val minStopAtr: Double = 0.6,
        val targetSessions: Int = 20
    )

    data class PolicyResult(
        val configuration: Map<String, String>,
        val source: ReproducibilityManifestFactory.SourceMetadata
    )

    fun resolve(input: RuntimeInput, retrievedAtUtc: Long): PolicyResult {
        require(input.retries >= 0) { "retries negativo" }
        require(retrievedAtUtc > 0L) { "retrievedAtUtc inválido" }
        val normalizedStatus = input.dataQualityStatus.trim().uppercase().ifBlank { "UNKNOWN" }
        val configuration = sortedMapOf(
            "policyVersion" to VERSION,
            "calendarVersion" to NyseSessionCalendar.VERSION,
            "quoteFreshnessVersion" to QuoteFreshnessEngine.VERSION,
            "setupClassifierVersion" to SetupClassificationEngine.VERSION,
            "structureRiskVersion" to StructureRiskEngine.VERSION,
            "aggressiveStopPolicyVersion" to AggressiveStopPolicy.VERSION,
            "macroRegimeVersion" to MacroRegimeEngine.VERSION,
            "fundamentalAssessmentVersion" to FundamentalAssessmentEngine.VERSION,
            "optionChainParserVersion" to YahooOptionChainParser.VERSION,
            "riskPct" to canonical(input.riskPct),
            "maxPositionPct" to canonical(input.maxPositionPct),
            "minRiskReward" to canonical(input.minRiskReward),
            "minStopAtr" to canonical(input.minStopAtr),
            "targetSessions" to input.targetSessions.toString()
        )
        return PolicyResult(
            configuration = configuration,
            source = ReproducibilityManifestFactory.SourceMetadata(
                provider = HISTORY_PROVIDER,
                providerHost = HISTORY_HOST,
                providerStatus = normalizedStatus,
                fallbackUsed = input.retries > 0,
                cacheHit = input.cacheHit,
                retrievedAtUtc = retrievedAtUtc
            )
        )
    }

    private fun canonical(value: Double): String = java.lang.String.format(java.util.Locale.US, "%.4f", value)
}
