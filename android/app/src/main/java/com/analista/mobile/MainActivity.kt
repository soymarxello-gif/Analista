package com.analista.mobile

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.analista.mobile.data.CandidateEntity
import com.analista.mobile.schedule.ScanScheduler
import com.analista.mobile.ui.MainViewModel
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

class MainActivity : ComponentActivity() {
    private val viewModel: MainViewModel by viewModels()
    override fun onCreate(savedInstanceState: Bundle?) { super.onCreate(savedInstanceState); ScanScheduler.scheduleNext(this); setContent { MaterialTheme { AnalistaScreen(viewModel) } } }
    @OptIn(ExperimentalMaterial3Api::class)
    @Composable private fun AnalistaScreen(vm: MainViewModel) {
        val runs by vm.runs.collectAsState(); val candidates by vm.candidates.collectAsState(); val running by vm.running.collectAsState(); val error by vm.error.collectAsState()
        val notificationLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }
        LaunchedEffect(Unit) { if (Build.VERSION.SDK_INT >= 33) notificationLauncher.launch(Manifest.permission.POST_NOTIFICATIONS) }
        Scaffold(topBar = { TopAppBar(title = { Text("Analista · Swing long-only") }) }) { padding ->
            LazyColumn(Modifier.fillMaxSize().padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                item { Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) { Text("Ejecución local autónoma", fontWeight = FontWeight.Bold); Text("NYSE · 09:20 America/New_York · Yahoo Finance"); Text("Próxima ejecución: ${formatTime(ScanScheduler.nextTrigger(this@MainActivity))}"); Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { Button(onClick = { vm.runNow() }, enabled = !running) { Text(if (running) "Ejecutando…" else "Ejecutar ahora") }; if (!ScanScheduler.canScheduleExact(this@MainActivity)) Button(onClick = { startActivity(ScanScheduler.permissionIntent(this@MainActivity)) }) { Text("Habilitar alarma exacta") } }; error?.let { Text(it, color = MaterialTheme.colorScheme.error) } } } }
                runs.firstOrNull()?.let { latest -> item { Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(16.dp)) { Text("Último scan", fontWeight = FontWeight.Bold); Text("${latest.marketDateEt} · ${latest.status} · ${latest.trustStatus}"); Text("Cobertura: ${latest.candidateCount} · fallos: ${latest.failureCount}") } } } }
                item { Text("Candidatos", style = MaterialTheme.typography.titleLarge) }
                if (candidates.isEmpty()) item { Text("Aún no hay resultados. Ejecuta el primer scan con Internet disponible.") }
                items(candidates, key = { it.id }) { CandidateCard(it) }
                if (runs.size > 1) { item { Text("Historial", style = MaterialTheme.typography.titleLarge) }; items(runs.take(20), key = { it.runId }) { run -> Card(onClick = { vm.selectRun(run.runId) }, modifier = Modifier.fillMaxWidth()) { Row(Modifier.padding(14.dp).fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { Text(run.marketDateEt); Text("${run.trustStatus} · ${run.candidateCount}") } } } }
            }
        }
    }
    @Composable private fun CandidateCard(candidate: CandidateEntity) { Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { Text(candidate.ticker, fontWeight = FontWeight.Bold); Text("${candidate.signal} · ${candidate.score}") }; Text("Cierre ${candidate.close} · RSI ${candidate.rsi14} · RVOL ${candidate.relativeVolume}"); Text("SMA20 ${candidate.sma20} · SMA50 ${candidate.sma50} · ATR ${candidate.atr14}"); candidate.entry?.let { Text("Entrada $it · Stop ${candidate.stop} · Objetivo ${candidate.target} · R/R ${candidate.rr}") }; Text(candidate.reason, style = MaterialTheme.typography.bodySmall) } } }
    private fun formatTime(epochMillis: Long): String = if (epochMillis <= 0) "no programada" else DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm z").withZone(ZoneId.of("America/New_York")).format(Instant.ofEpochMilli(epochMillis))
}
