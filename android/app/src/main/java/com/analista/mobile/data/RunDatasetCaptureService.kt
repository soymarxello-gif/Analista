package com.analista.mobile.data

import com.analista.mobile.domain.FundamentalAssessmentEngine
import com.analista.mobile.domain.LiveUniverseSnapshotAssembler

class RunDatasetCaptureService(private val store: RunDatasetStore) {
    suspend fun capture(
        runId: String,
        effectiveDate: String,
        tickers: List<String>,
        barsByTicker: Map<String, List<PriceBar>>,
        quotesByTicker: Map<String, MarketQuote>,
        macroSnapshots: List<MarketSnapshotEntity>,
        createdAtUtc: Long
    ): List<RunDatasetArtifactEntity> {
        require(runId.isNotBlank())
        require(effectiveDate.isNotBlank())
        require(createdAtUtc > 0L)
        val normalizedTickers = tickers.map(::normalizeTicker).filter { it.isNotBlank() }.distinct().sorted()
        require(normalizedTickers.isNotEmpty())

        val artifacts = mutableListOf<RunDatasetArtifactEntity>()
        for (ticker in normalizedTickers) {
            barsByTicker[ticker]?.takeIf { it.isNotEmpty() }?.let { bars ->
                artifacts += store.write(
                    runId = runId,
                    datasetType = "NORMALIZED_BARS",
                    ticker = ticker,
                    payload = NormalizedDatasetCodec.bars(ticker, bars),
                    createdAtUtc = createdAtUtc
                )
            }
            artifacts += store.write(
                runId = runId,
                datasetType = "EXECUTION_QUOTE",
                ticker = ticker,
                payload = NormalizedDatasetCodec.quote(ticker, quotesByTicker[ticker]),
                createdAtUtc = createdAtUtc
            )
            FundamentalSnapshotRegistry.get(ticker)?.let { registered ->
                val entity = FundamentalAssessmentEngine.toEntity(
                    runId = runId,
                    ticker = ticker,
                    metrics = registered.metrics,
                    capturedAtUtc = registered.capturedAtUtc
                )
                artifacts += store.write(
                    runId = runId,
                    datasetType = "FUNDAMENTAL_SNAPSHOT",
                    ticker = ticker,
                    payload = NormalizedDatasetCodec.fundamentals(listOf(entity)),
                    createdAtUtc = createdAtUtc
                )
            }
            OptionChainRegistry.get(ticker)?.let { chain ->
                artifacts += store.write(
                    runId = runId,
                    datasetType = "OPTION_CHAIN",
                    ticker = ticker,
                    payload = NormalizedDatasetCodec.options(chain),
                    createdAtUtc = createdAtUtc
                )
            }
        }

        if (macroSnapshots.isNotEmpty()) {
            artifacts += store.write(
                runId = runId,
                datasetType = "MACRO_SNAPSHOT",
                ticker = null,
                payload = NormalizedDatasetCodec.macro(macroSnapshots),
                createdAtUtc = createdAtUtc
            )
            macroSnapshots.map { it.symbol }.distinct().sorted().forEach { symbol ->
                MarketHistoryRegistry.get(symbol)?.takeIf { it.isNotEmpty() }?.let { bars ->
                    artifacts += store.write(
                        runId = runId,
                        datasetType = "MACRO_HISTORY",
                        ticker = symbol,
                        payload = NormalizedDatasetCodec.bars(symbol, bars),
                        createdAtUtc = createdAtUtc
                    )
                }
            }
        }

        val liveUniverse = LiveUniverseSnapshotAssembler.assemble(
            runId = runId,
            fallbackUniverse = normalizedTickers,
            effectiveDate = effectiveDate,
            createdAtUtc = createdAtUtc
        )
        artifacts += store.write(
            runId = runId,
            datasetType = "UNIVERSE_SNAPSHOT",
            ticker = null,
            payload = NormalizedDatasetCodec.universe(
                liveUniverse.bundle.snapshot,
                liveUniverse.bundle.members
            ),
            createdAtUtc = createdAtUtc
        )

        return artifacts.sortedWith(
            compareBy<RunDatasetArtifactEntity> { it.datasetType }
                .thenBy { it.ticker ?: "" }
                .thenBy { it.contentHash }
        )
    }

    private fun normalizeTicker(value: String): String = value.trim().uppercase().replace(".", "-")

    companion object {
        const val VERSION = "live-dataset-capture-2"
    }
}
