package com.analista.mobile.data

import com.analista.mobile.domain.TechnicalEngine
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.UUID
import kotlin.math.round

class ScanRepository(
    private val dao: AnalistaDao,
    private val yahoo: YahooFinanceClient,
    private val tickers: List<String> = DEFAULT_TICKERS
) {
    suspend fun runScan(): ScanRunEntity = coroutineScope {
        val started = System.currentTimeMillis()
        val semaphore = Semaphore(4)
        var failures = 0
        var cacheHits = 0
        var retries = 0
        val candidates = tickers.map { ticker ->
            async {
                runCatching {
                    semaphore.withPermit {
                        val fetched = yahoo.dailyHistory(ticker)
                        synchronized(this@ScanRepository) {
                            if (fetched.cacheHit) cacheHits += 1
                            retries += fetched.retries
                        }
                        TechnicalEngine.analyze(ticker, fetched.bars)
                    }
                }.onFailure { synchronized(this@ScanRepository) { failures += 1 } }.getOrNull()
            }
        }.awaitAll().filterNotNull().sortedByDescending { it.score }

        val runId = DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss").withZone(ZoneId.of("UTC"))
            .format(Instant.ofEpochMilli(started)) + "-" + UUID.randomUUID().toString().take(8)
        val marketDate = LocalDate.now(ZoneId.of("America/New_York")).toString()
        val trust = when {
            candidates.isEmpty() -> "UNUSABLE"
            failures > tickers.size / 2 -> "UNUSABLE"
            failures > 0 || cacheHits > 0 -> "DEGRADED"
            else -> "TRUSTED"
        }
        val finished = System.currentTimeMillis()
        val run = ScanRunEntity(
            runId = runId, startedAtUtc = started, finishedAtUtc = finished,
            marketDateEt = marketDate,
            status = if (candidates.isEmpty()) "FAILED_DATA_SOURCE" else "COMPLETED",
            trustStatus = trust, candidateCount = candidates.size, failureCount = failures,
            source = if (cacheHits > 0) "Yahoo Finance + cache" else "Yahoo Finance",
            durationMs = finished - started, cacheHitCount = cacheHits, retryCount = retries
        )
        val rows = candidates.map {
            CandidateEntity(
                runId = runId, ticker = it.ticker, signal = it.signal, score = it.score,
                close = it.close, sma20 = it.sma20, sma50 = it.sma50, rsi14 = it.rsi14,
                macd = it.macd, macdSignal = it.macdSignal, stochastic = it.stochastic,
                atr14 = it.atr14, relativeVolume = it.relativeVolume, entry = it.entry,
                stop = it.stop, target = it.target, rr = it.rr, reason = it.reason
            )
        }
        val snapshots = fetchMacro(runId, semaphore)
        dao.saveRun(run, rows, snapshots)
        updateBacktestOutcomes(runId, rows)
        run
    }

    private suspend fun fetchMacro(runId: String, semaphore: Semaphore): List<MarketSnapshotEntity> = coroutineScope {
        MACRO_SYMBOLS.map { (symbol, label) ->
            async {
                runCatching {
                    semaphore.withPermit {
                        val bars = yahoo.dailyHistory(symbol, "3mo").bars
                        val latest = bars.last().close
                        val previous = bars.dropLast(1).last().close
                        MarketSnapshotEntity(
                            snapshotId = "$runId-$symbol", runId = runId, symbol = symbol, label = label,
                            close = round2(latest), changePct = round2((latest / previous - 1.0) * 100.0),
                            capturedAtUtc = System.currentTimeMillis()
                        )
                    }
                }.getOrNull()
            }
        }.awaitAll().filterNotNull()
    }

    private suspend fun updateBacktestOutcomes(currentRunId: String, current: List<CandidateEntity>) {
        val latestByTicker = current.associateBy { it.ticker }
        val outcomes = dao.priorCandidates(currentRunId)
            .distinctBy { it.runId to it.ticker }
            .mapNotNull { prior ->
                val latest = latestByTicker[prior.ticker] ?: return@mapNotNull null
                BacktestOutcomeEntity(
                    outcomeId = "${prior.runId}-${prior.ticker}", sourceRunId = prior.runId,
                    ticker = prior.ticker, signal = prior.signal, sourceClose = prior.close,
                    latestClose = latest.close, returnPct = round2((latest.close / prior.close - 1.0) * 100.0),
                    evaluatedAtUtc = System.currentTimeMillis()
                )
            }
        if (outcomes.isNotEmpty()) dao.insertOutcomes(outcomes)
    }

    fun observeRuns(): Flow<List<ScanRunEntity>> = dao.observeRuns()
    fun observeCandidates(runId: String): Flow<List<CandidateEntity>> = dao.observeCandidates(runId)
    fun observeMarketSnapshots(runId: String): Flow<List<MarketSnapshotEntity>> = dao.observeMarketSnapshots(runId)
    fun observeOutcomes(): Flow<List<BacktestOutcomeEntity>> = dao.observeOutcomes()

    companion object {
        val DEFAULT_TICKERS = listOf(
            "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA",
            "JPM", "V", "MA", "COST", "LLY", "NFLX", "AMD", "CRM", "ORCL", "PLTR",
            "UBER", "PANW", "CRWD", "NOW", "MU", "QCOM", "INTC", "AMAT", "LRCX",
            "CAT", "GE", "RTX", "XOM", "CVX", "WMT", "HD", "UNH"
        )
        val MACRO_SYMBOLS = listOf(
            "^TNX" to "US10Y", "^TYX" to "US30Y", "^VIX" to "VIX",
            "DX-Y.NYB" to "DXY", "CL=F" to "WTI", "BTC-USD" to "Bitcoin"
        )
        private fun round2(value: Double) = round(value * 100.0) / 100.0
    }
}
