package com.analista.mobile.data

import com.analista.mobile.domain.DeterministicReplayEngine
import kotlinx.coroutines.flow.Flow

class RunReplayService(
    private val dao: ReplayDao,
    private val store: RunDatasetStore
) {
    suspend fun replay(runId: String, evaluatedAtUtc: Long = System.currentTimeMillis()): ReplayResultEntity {
        val normalizedRunId = runId.trim()
        require(normalizedRunId.isNotBlank())
        require(evaluatedAtUtc > 0L)
        val result = runCatching { execute(normalizedRunId) }
            .fold(
                onSuccess = { summary -> summary.toEntity(evaluatedAtUtc) },
                onFailure = { error -> failure(normalizedRunId, error, evaluatedAtUtc) }
            )
        dao.upsertReplayResult(result)
        return result
    }

    fun observe(runId: String): Flow<ReplayResultEntity?> = dao.observeReplayResult(runId)

    private suspend fun execute(runId: String): DeterministicReplayEngine.Summary {
        val run = dao.getRun(runId) ?: error("missing_scan_run")
        val definition = dao.getRunDefinition(runId) ?: error("missing_run_definition")
        val artifacts = dao.getArtifacts(runId)
        if (artifacts.isEmpty()) error("missing_dataset_artifacts")
        require(artifacts.all { it.runId == runId })
        require(artifacts.map { it.artifactId }.distinct().size == artifacts.size)

        val bars = mutableMapOf<String, List<PriceBar>>()
        val quotes = mutableMapOf<String, MarketQuote?>()
        val macroSnapshots = mutableListOf<MarketSnapshotEntity>()
        val macroHistories = mutableMapOf<String, List<PriceBar>>()
        val fundamentals = mutableMapOf<String, FundamentalSnapshotEntity>()
        val options = mutableMapOf<String, OptionChainSnapshot>()
        val insiders = mutableMapOf<String, InsiderTransactionRegistry.Snapshot>()
        var universe: NormalizedDatasetDecoder.UniverseDataset? = null

        for (artifact in artifacts) {
            val payload = store.read(artifact)
            when (artifact.datasetType) {
                "NORMALIZED_BARS" -> {
                    val decoded = NormalizedDatasetDecoder.bars(payload)
                    require(decoded.ticker == artifact.ticker)
                    require(bars.put(decoded.ticker, decoded.bars) == null) { "duplicate_normalized_bars" }
                }
                "EXECUTION_QUOTE" -> {
                    val decoded = NormalizedDatasetDecoder.quote(payload)
                    require(decoded.ticker == artifact.ticker)
                    require(!quotes.containsKey(decoded.ticker)) { "duplicate_execution_quote" }
                    quotes[decoded.ticker] = decoded.quote
                }
                "MACRO_SNAPSHOT" -> {
                    require(artifact.ticker == null)
                    macroSnapshots += NormalizedDatasetDecoder.macro(payload, runId)
                }
                "MACRO_HISTORY" -> {
                    val decoded = NormalizedDatasetDecoder.bars(payload)
                    require(decoded.ticker == artifact.ticker)
                    require(macroHistories.put(decoded.ticker, decoded.bars) == null) { "duplicate_macro_history" }
                }
                "FUNDAMENTAL_SNAPSHOT" -> {
                    val decoded = NormalizedDatasetDecoder.fundamentals(payload, runId)
                    require(decoded.size == 1)
                    val row = decoded.single()
                    require(row.ticker == artifact.ticker)
                    require(fundamentals.put(row.ticker, row) == null) { "duplicate_fundamental_snapshot" }
                }
                "OPTION_CHAIN" -> {
                    val decoded = NormalizedDatasetDecoder.options(payload)
                    require(decoded.ticker == artifact.ticker)
                    require(options.put(decoded.ticker, decoded) == null) { "duplicate_option_chain" }
                }
                "INSIDER_TRANSACTIONS" -> {
                    val decoded = NormalizedDatasetDecoder.insiders(payload)
                    require(decoded.ticker == artifact.ticker)
                    require(insiders.put(decoded.ticker, decoded) == null) { "duplicate_insider_transactions" }
                }
                "UNIVERSE_SNAPSHOT" -> {
                    require(artifact.ticker == null)
                    require(universe == null) { "duplicate_universe_snapshot" }
                    universe = NormalizedDatasetDecoder.universe(payload)
                }
                else -> error("unsupported_dataset_type:${artifact.datasetType}")
            }
        }

        val resolvedUniverse = universe ?: error("missing_universe_snapshot")
        return DeterministicReplayEngine.replay(
            stored = DeterministicReplayEngine.StoredRun(
                run = run,
                definition = definition,
                manifests = dao.getManifests(runId),
                candidates = dao.getCandidates(runId),
                enrichments = dao.getEnrichment(runId),
                analyses = dao.getAnalysis(runId),
                tradePlans = dao.getTradePlans(runId),
                finalDecisions = dao.getFinalDecisions(runId)
            ),
            datasets = DeterministicReplayEngine.DatasetBundle(
                barsByTicker = bars,
                quotesByTicker = quotes,
                macroSnapshots = macroSnapshots.distinctBy { it.symbol }.sortedBy { it.symbol },
                macroHistories = macroHistories,
                fundamentalsByTicker = fundamentals,
                optionsByTicker = options,
                universe = resolvedUniverse,
                insidersByTicker = insiders
            )
        )
    }

    private fun DeterministicReplayEngine.Summary.toEntity(evaluatedAtUtc: Long) = ReplayResultEntity(
        replayId = "$runId-${engineVersion}",
        runId = runId,
        status = status,
        expectedTickers = expectedTickers,
        replayedTickers = replayedTickers,
        fullyMatchedTickers = fullyMatchedTickers,
        mismatchedTickers = mismatchedTickers,
        missingDatasetCount = missingDatasetCount,
        reasons = reasons.joinToString("|"),
        tickerDetails = tickerResults.joinToString(";") { row ->
            "${row.ticker}:${row.reasons.joinToString(",").ifBlank { "MATCH" }}"
        },
        engineVersion = engineVersion,
        evaluatedAtUtc = evaluatedAtUtc
    )

    private fun failure(runId: String, error: Throwable, evaluatedAtUtc: Long) = ReplayResultEntity(
        replayId = "$runId-${DeterministicReplayEngine.VERSION}",
        runId = runId,
        status = "INVALID",
        expectedTickers = 0,
        replayedTickers = 0,
        fullyMatchedTickers = 0,
        mismatchedTickers = 0,
        missingDatasetCount = 1,
        reasons = listOfNotNull("replay_service_error", error.message?.take(240)).joinToString("|"),
        tickerDetails = "",
        engineVersion = DeterministicReplayEngine.VERSION,
        evaluatedAtUtc = evaluatedAtUtc
    )

    companion object {
        const val VERSION = "run-replay-service-2"
    }
}
