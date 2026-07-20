package com.analista.mobile.domain

object ScanReproducibilityPolicy {
    const val VERSION = "scan-repro-policy-14"
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
        require(input.riskPct > 0.0)
        require(input.maxPositionPct > 0.0)
        require(input.minRiskReward > 0.0)
        require(input.minStopAtr > 0.0)
        require(input.targetSessions in 4..21)
        val normalizedStatus = input.dataQualityStatus.trim().uppercase().ifBlank { "UNKNOWN" }
        val configuration = CanonicalEngineConfiguration.create(
            policyVersion = VERSION,
            riskPct = input.riskPct,
            maxPositionPct = input.maxPositionPct,
            minRiskReward = input.minRiskReward,
            minStopAtr = input.minStopAtr,
            targetSessions = input.targetSessions
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
}
