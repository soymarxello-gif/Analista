package com.analista.mobile.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.analista.mobile.AnalistaApplication
import com.analista.mobile.data.AlpacaCredentialsStore
import com.analista.mobile.data.BacktestOutcomeEntity
import com.analista.mobile.data.CandidateAnalysisEntity
import com.analista.mobile.data.CandidateEntity
import com.analista.mobile.data.CandidateEnrichmentEntity
import com.analista.mobile.data.CandidateTradePlanEntity
import com.analista.mobile.data.MarketSnapshotEntity
import com.analista.mobile.data.RankingComparisonEntity
import com.analista.mobile.data.ReproducibilityManifestEntity
import com.analista.mobile.data.ScanRepository
import com.analista.mobile.data.ScanRunEntity
import com.analista.mobile.data.TradeOutcomeEntity
import com.analista.mobile.domain.ReproducibilityDiagnosticsEngine
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val app = application as AnalistaApplication
    private val repository = app.repository
    private val dao = app.database.dao()
    val runs: StateFlow<List<ScanRunEntity>> = repository.observeRuns()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    private val selectedRunId = MutableStateFlow<String?>(null)
    val candidates: StateFlow<List<CandidateEntity>> = selectedRunId
        .flatMapLatest { id -> if (id == null) flowOf(emptyList()) else repository.observeCandidates(id) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val macro: StateFlow<List<MarketSnapshotEntity>> = selectedRunId
        .flatMapLatest { id -> if (id == null) flowOf(emptyList()) else repository.observeMarketSnapshots(id) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val enrichment: StateFlow<List<CandidateEnrichmentEntity>> = selectedRunId
        .flatMapLatest { id -> if (id == null) flowOf(emptyList()) else repository.observeEnrichment(id) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val analysis: StateFlow<List<CandidateAnalysisEntity>> = selectedRunId
        .flatMapLatest { id -> if (id == null) flowOf(emptyList()) else repository.observeAnalysis(id) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val tradePlans: StateFlow<List<CandidateTradePlanEntity>> = selectedRunId
        .flatMapLatest { id -> if (id == null) flowOf(emptyList()) else repository.observeTradePlans(id) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val reproducibilityManifests: StateFlow<List<ReproducibilityManifestEntity>> = selectedRunId
        .flatMapLatest { id -> if (id == null) flowOf(emptyList()) else repository.observeReproducibilityManifests(id) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val rankingComparison: StateFlow<RankingComparisonEntity?> = selectedRunId
        .flatMapLatest { id -> if (id == null) flowOf(null) else dao.observeRankingComparison(id) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
    val rankingDiagnostics: StateFlow<RankingDiagnosticsPresenter.Model> = rankingComparison
        .map(RankingDiagnosticsPresenter::present)
        .stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5_000),
            RankingDiagnosticsPresenter.present(null)
        )
    val reproducibilitySummary: StateFlow<ReproducibilityDiagnosticsEngine.Summary> =
        combine(reproducibilityManifests, rankingDiagnostics) { manifests, ranking ->
            val base = ReproducibilityDiagnosticsEngine.summarize(ScanRepository.DEFAULT_TICKERS.size, manifests)
            base.copy(
                providers = base.providers + ranking.compactLabel,
                status = "${base.status} · ${ranking.status}"
            )
        }.stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5_000),
            ReproducibilityDiagnosticsEngine.summarize(ScanRepository.DEFAULT_TICKERS.size, emptyList()).copy(
                providers = setOf(RankingDiagnosticsPresenter.present(null).compactLabel),
                status = "INCOMPLETE · NO_DATA"
            )
        )
    val outcomes: StateFlow<List<BacktestOutcomeEntity>> = repository.observeOutcomes()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val tradeOutcomes: StateFlow<List<TradeOutcomeEntity>> = repository.observeTradeOutcomes()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val running = MutableStateFlow(false)
    val error = MutableStateFlow<String?>(null)
    val alpacaConfigured = MutableStateFlow(repository.alpacaCredentials() != null)
    val alpacaFeed = MutableStateFlow(repository.alpacaCredentials()?.feed ?: "iex")
    val alpacaStatus = MutableStateFlow("NO_PROBADO")
    val testingAlpaca = MutableStateFlow(false)

    init {
        viewModelScope.launch {
            runs.collect { list ->
                if (selectedRunId.value == null) selectedRunId.value = list.firstOrNull()?.runId
            }
        }
    }

    fun selectRun(runId: String) { selectedRunId.value = runId }

    fun runNow() {
        if (running.value) return
        viewModelScope.launch {
            running.value = true
            error.value = null
            runCatching { repository.runScan() }
                .onSuccess { selectedRunId.value = it.runId }
                .onFailure { error.value = it.message ?: "Error desconocido" }
            running.value = false
        }
    }

    fun saveAndTestAlpaca(apiKey: String, secretKey: String, feed: String) {
        if (testingAlpaca.value) return
        viewModelScope.launch {
            testingAlpaca.value = true
            val credentials = AlpacaCredentialsStore.Credentials(apiKey.trim(), secretKey.trim(), feed)
            runCatching {
                require(credentials.apiKey.isNotBlank() && credentials.secretKey.isNotBlank()) { "Credenciales incompletas" }
                val result = repository.testAlpaca(credentials)
                alpacaStatus.value = result.status
                if (result.ok) {
                    repository.saveAlpaca(credentials)
                    alpacaConfigured.value = true
                    alpacaFeed.value = feed
                }
            }.onFailure { alpacaStatus.value = it.message ?: "ERROR" }
            testingAlpaca.value = false
        }
    }

    fun clearAlpaca() {
        repository.clearAlpaca()
        alpacaConfigured.value = false
        alpacaFeed.value = "iex"
        alpacaStatus.value = "BORRADO"
    }
}
