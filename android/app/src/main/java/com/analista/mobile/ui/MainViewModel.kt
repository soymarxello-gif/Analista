package com.analista.mobile.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.analista.mobile.AnalistaApplication
import com.analista.mobile.data.CandidateEntity
import com.analista.mobile.data.ScanRunEntity
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = (application as AnalistaApplication).repository
    val runs: StateFlow<List<ScanRunEntity>> = repository.observeRuns().stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    private val selectedRunId = MutableStateFlow<String?>(null)
    val candidates: StateFlow<List<CandidateEntity>> = selectedRunId.flatMapLatest { id -> if (id == null) flowOf(emptyList()) else repository.observeCandidates(id) }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val running = MutableStateFlow(false); val error = MutableStateFlow<String?>(null)
    init { viewModelScope.launch { runs.collect { list -> if (selectedRunId.value == null) selectedRunId.value = list.firstOrNull()?.runId } } }
    fun selectRun(runId: String) { selectedRunId.value = runId }
    fun runNow() { if (running.value) return; viewModelScope.launch { running.value = true; error.value = null; runCatching { repository.runScan() }.onSuccess { selectedRunId.value = it.runId }.onFailure { error.value = it.message ?: "Error desconocido" }; running.value = false } }
}
