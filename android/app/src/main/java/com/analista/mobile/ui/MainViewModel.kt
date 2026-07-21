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
import com.analista.mobile.data.FinalDecisionEntity
import com.analista.mobile.data.MarketSnapshotEntity
import com.analista.mobile.data.RankingComparisonEntity
import com.analista.mobile.data.ReplayResultEntity
import com.analista.mobile.data.ReproducibilityManifestEntity
import com.analista.mobile.data.RunDatasetArtifactEntity
import com.analista.mobile.data.RunDefinitionEntity
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
    val finalDecisions: StateFlow<List<FinalDecisionEntity>> = selectedRunId
        .flatMapLatest { id -> if (id == null) flowOf(emptyList()) else repository.observeFinalDecisions(id) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val tradePlans: StateFlow<List<CandidateTradePlanEntity>> = selectedRunId
        .flatMapLatest { id -> if (id == null) flowOf(emptyList()) else repository.observeTradePlans(id) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val datasetArtifacts: StateFlow<List<RunDatasetArtifactEntity>> = selectedRunId
        .flatMapLatest { id -> if (id == null) flowOf(emptyList()) else repository.observeRunDatasetArtifacts(id) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val reproducibilityManifests: StateFlow<List<ReproducibilityManifestEntity>> = selectedRunId
        .flatMapLatest { id -> if (id == null) flowOf(emptyList()) else repository.observeReproducibilityManifests(id) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val runDefinition: StateFlow<RunDefinitionEntity?> = selectedRunId
        .flatMapLatest { id -> if (id == null) flowOf(null) else dao.observeRunDefinition(id) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
    val rankingComparison: StateFlow<RankingComparisonEntity?> = selectedRunId
        .flatMapLatest { id -> if (id == null) flowOf(null) else dao.observeRankingComparison(id) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
    val replayResult: StateFlow<ReplayResultEntity?> = selectedRunId
        .flatMapLatest { id -> if (id == null) flowOf(null) else app.replayService.observe(id) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
    val replayDiagnostics: StateFlow<ReplayDiagnosticsPresenter.Model> = replayResult
        .map(ReplayDiagnosticsPresenter::present)
        .stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5_000),
            ReplayDiagnosticsPresenter.present(null)
        )
    val rankingDiagnostics: StateFlow<RankingDiagnosticsPresenter.Model> = rankingComparison
        .map(RankingDiagnosticsPresenter::present)
        .stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5_000),
            RankingDiagnosticsPresenter.present(null)
        )
    val reproducibilitySummary: StateFlow<ReproducibilityDiagnosticsEngine.Summary> =
        combine(
            reproducibilityManifests,
            rankingDiagnostics,
            runDefinition,
            replayDiagnostics
        ) { manifests, ranking, definition, replay ->
            val expected = definition?.universeSymbols
                ?.split(',')
                ?.count { it.isNotBlank() }
                ?.takeIf { it > 0 }
                ?: candidates.value.size.coerceAtLeast(ScanRepository.DEFAULT_TICKERS.size)
            val base = ReproducibilityDiagnosticsEngine.summarize(expected, manifests)
            val definitionLabels = if (definition == null) {
                setOf("Definición: NO_DATA")
            } else {
                setOf(
                    "Universo ${definition.universeVersion}",
                    "Config ${definition.configurationVersion}",
                    "Motores ${definition.engineBundleVersion}"
                )
            }
            base.copy(
                providers = base.providers + ranking.compactLabel + definitionLabels + "Replay ${replay.status}",
                status = "${base.status} · ${ranking.status} · ${if (definition == null) "NO_DEFINITION" else "DEFINED"} · REPLAY_${replay.status}"
            )
        }.stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5_000),
            ReproducibilityDiagnosticsEngine.summarize(ScanRepository.DEFAULT_TICKERS.size, emptyList()).copy(
                providers = setOf(
                    RankingDiagnosticsPresenter.present(null).compactLabel,
                    "Definición: NO_DATA",
                    "Replay NO_DATA"
                ),
                status = "INCOMPLETE · NO_DATA · NO_DEFINITION · REPLAY_NO_DATA"
            )
        )
    val outcomes: StateFlow<List<BacktestOutcomeEntity>> = repository.observeOutcomes()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val tradeOutcomes: StateFlow<List<TradeOutcomeEntity>> = repository.observeTradeOutcomes()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val running = MutableStateFlow(false)
    val replayRunning = MutableStateFlow(false)
    val error = MutableStateFlow<String?>(null)
    val alpacaConfigured = MutableStateFlow(repository.alpacaCredentials() != null)
    val alpacaFeed = MutableStateFlow(repository.alpacaCredentials()?.feed ?: "iex")
    val alpacaStatus = MutableStateFlow("NO_PROBADO")
    val testingAlpaca = MutableStateFlow(false)
    val universeStatus = MutableStateFlow("NO_PREPARADO")
    val universeSource = MutableStateFlow("NONE")
    val universeCount = MutableStateFlow(0)
    val officialSources = MutableStateFlow(
        OfficialSourceUiState.fromSettings(app.officialSourceCoordinator.loadSettings())
    )
    val refreshingOfficialSources = MutableStateFlow(false)

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
            runCatching {
                val universe = app.dynamicScanCoordinator.prepare()
                officialSources.value = OfficialSourceUiState.fromSettings(app.officialSourceCoordinator.loadSettings()).copy(
                    status = "REFRESHED_BEFORE_SCAN",
                    refreshedAtUtc = System.currentTimeMillis()
                )
                universeStatus.value = universe.status
                universeSource.value = universe.source
                universeCount.value = universe.symbols.size
                repository.runScan()
            }
                .onSuccess { run ->
                    selectedRunId.value = run.runId
                    replayRunning.value = true
                    app.replayService.replay(run.runId)
                    replayRunning.value = false
                }
                .onFailure {
                    replayRunning.value = false
                    error.value = it.message ?: "Error desconocido"
                }
            running.value = false
        }
    }

    fun replaySelected() {
        val runId = selectedRunId.value ?: return
        if (replayRunning.value) return
        viewModelScope.launch {
            replayRunning.value = true
            error.value = null
            runCatching { app.replayService.replay(runId) }
                .onFailure { error.value = it.message ?: "Error de replay" }
            replayRunning.value = false
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
        universeStatus.value = "NO_PREPARADO"
        universeSource.value = "NONE"
        universeCount.value = 0
    }

    fun saveAndRefreshOfficialSources(fredApiKey: String, secContactEmail: String) {
        if (refreshingOfficialSources.value) return
        viewModelScope.launch {
            refreshingOfficialSources.value = true
            error.value = null
            runCatching {
                fredApiKey.trim().takeIf { it.isNotBlank() }?.let(app.officialSourceCoordinator::saveFredApiKey)
                secContactEmail.trim().takeIf { it.isNotBlank() }?.let(app.officialSourceCoordinator::saveSecContactEmail)
                val result = app.officialSourceCoordinator.refresh()
                officialSources.value = OfficialSourceUiState.fromResult(
                    app.officialSourceCoordinator.loadSettings(),
                    result
                )
            }.onFailure {
                error.value = it.message ?: "Error al actualizar fuentes oficiales"
                officialSources.value = OfficialSourceUiState.fromSettings(app.officialSourceCoordinator.loadSettings()).copy(
                    status = "ERROR"
                )
            }
            refreshingOfficialSources.value = false
        }
    }

    fun refreshOfficialSources() = saveAndRefreshOfficialSources("", "")

    fun clearFredApiKey() {
        app.officialSourceCoordinator.clearFredApiKey()
        officialSources.value = OfficialSourceUiState.fromSettings(app.officialSourceCoordinator.loadSettings()).copy(
            status = "FRED_BORRADO"
        )
    }

    fun clearSecContactEmail() {
        app.officialSourceCoordinator.clearSecContactEmail()
        officialSources.value = OfficialSourceUiState.fromSettings(app.officialSourceCoordinator.loadSettings()).copy(
            status = "SEC_BORRADO"
        )
    }
}
