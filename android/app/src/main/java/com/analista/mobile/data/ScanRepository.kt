package com.analista.mobile.data

import com.analista.mobile.domain.TechnicalEngine
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.UUID

class ScanRepository(private val dao: AnalistaDao, private val yahoo: YahooFinanceClient, private val tickers: List<String> = DEFAULT_TICKERS) {
    suspend fun runScan(): ScanRunEntity = coroutineScope {
        val started = System.currentTimeMillis(); val semaphore = Semaphore(4); var failures = 0
        val candidates = tickers.map { ticker -> async { runCatching { semaphore.withPermit { TechnicalEngine.analyze(ticker, yahoo.dailyHistory(ticker)) } }.onFailure { synchronized(this@ScanRepository) { failures += 1 } }.getOrNull() } }.awaitAll().filterNotNull().sortedByDescending { it.score }
        val runId = DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss").withZone(ZoneId.of("UTC")).format(Instant.ofEpochMilli(started)) + "-" + UUID.randomUUID().toString().take(8)
        val trust = when { candidates.isEmpty() -> "UNUSABLE"; failures > tickers.size / 2 -> "UNUSABLE"; failures > 0 -> "DEGRADED"; else -> "TRUSTED" }
        val run = ScanRunEntity(runId, started, System.currentTimeMillis(), LocalDate.now(ZoneId.of("America/New_York")).toString(), if (candidates.isEmpty()) "FAILED_DATA_SOURCE" else "COMPLETED", trust, candidates.size, failures)
        val rows = candidates.map { CandidateEntity(runId = runId, ticker = it.ticker, signal = it.signal, score = it.score, close = it.close, sma20 = it.sma20, sma50 = it.sma50, rsi14 = it.rsi14, macd = it.macd, macdSignal = it.macdSignal, stochastic = it.stochastic, atr14 = it.atr14, relativeVolume = it.relativeVolume, entry = it.entry, stop = it.stop, target = it.target, rr = it.rr, reason = it.reason) }
        dao.saveRun(run, rows); run
    }
    fun observeRuns() = dao.observeRuns()
    fun observeCandidates(runId: String) = dao.observeCandidates(runId)
    companion object { val DEFAULT_TICKERS = listOf("AAPL","MSFT","NVDA","AMZN","GOOGL","META","AVGO","TSLA","JPM","V","MA","COST","LLY","NFLX","AMD","CRM","ORCL","PLTR","UBER","PANW","CRWD","NOW","MU","QCOM","INTC","AMAT","LRCX","CAT","GE","RTX","XOM","CVX","WMT","HD","UNH") }
}
