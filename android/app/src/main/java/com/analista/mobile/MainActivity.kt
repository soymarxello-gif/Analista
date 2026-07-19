package com.analista.mobile

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.analista.mobile.data.BacktestOutcomeEntity
import com.analista.mobile.data.CandidateEntity
import com.analista.mobile.data.CandidateEnrichmentEntity
import com.analista.mobile.data.MarketSnapshotEntity
import com.analista.mobile.data.ScanRunEntity
import com.analista.mobile.schedule.DiagnosticsStore
import com.analista.mobile.schedule.ScanScheduler
import com.analista.mobile.ui.MainViewModel
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

class MainActivity : ComponentActivity() {
    private val viewModel: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ScanScheduler.scheduleNext(this)
        setContent { MaterialTheme { AnalistaApp(viewModel) } }
    }

    @OptIn(ExperimentalMaterial3Api::class)
    @Composable
    private fun AnalistaApp(vm: MainViewModel) {
        val runs by vm.runs.collectAsState()
        val candidates by vm.candidates.collectAsState()
        val macro by vm.macro.collectAsState()
        val enrichment by vm.enrichment.collectAsState()
        val outcomes by vm.outcomes.collectAsState()
        val running by vm.running.collectAsState()
        val error by vm.error.collectAsState()
        var tab by remember { mutableIntStateOf(0) }
        val notificationLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }
        LaunchedEffect(Unit) {
            if (Build.VERSION.SDK_INT >= 33) notificationLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        val labels = listOf("Resumen", "Historial", "Backtest", "Diagnóstico")
        Scaffold(
            topBar = { TopAppBar(title = { Text("Analista · Swing long-only") }) },
            bottomBar = {
                NavigationBar {
                    labels.forEachIndexed { index, label ->
                        NavigationBarItem(
                            selected = tab == index,
                            onClick = { tab = index },
                            icon = { Text(listOf("◉", "◷", "↗", "⚙")[index]) },
                            label = { Text(label) }
                        )
                    }
                }
            }
        ) { padding ->
            when (tab) {
                0 -> SummaryScreen(runs, candidates, enrichment, macro, running, error, vm::runNow, Modifier.padding(padding))
                1 -> HistoryScreen(runs, vm::selectRun, Modifier.padding(padding))
                2 -> BacktestScreen(outcomes, Modifier.padding(padding))
                else -> DiagnosticsScreen(Modifier.padding(padding))
            }
        }
    }

    @Composable
    private fun SummaryScreen(
        runs: List<ScanRunEntity>,
        candidates: List<CandidateEntity>,
        enrichment: List<CandidateEnrichmentEntity>,
        macro: List<MarketSnapshotEntity>,
        running: Boolean,
        error: String?,
        runNow: () -> Unit,
        modifier: Modifier
    ) {
        LazyColumn(modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Ejecución local autónoma", fontWeight = FontWeight.Bold)
                        Text("NYSE · 09:20 America/New_York · Yahoo Finance")
                        Text("Próxima ejecución: ${formatTime(ScanScheduler.nextTrigger(this@MainActivity))}")
                        Button(onClick = runNow, enabled = !running) { Text(if (running) "Ejecutando…" else "Ejecutar ahora") }
                        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                    }
                }
            }
            runs.firstOrNull()?.let { latest -> item { RunCard(latest) } }
            if (macro.isNotEmpty()) {
                item { Text("Contexto macro", style = MaterialTheme.typography.titleLarge) }
                items(macro, key = { it.snapshotId }) { MacroCard(it) }
            }
            item { Text("Candidatos", style = MaterialTheme.typography.titleLarge) }
            if (candidates.isEmpty()) item { Text("Aún no hay resultados para esta ejecución.") }
            val enrichmentByTicker = enrichment.associateBy { it.ticker }
            items(candidates, key = { it.id }) { CandidateCard(it, enrichmentByTicker[it.ticker]) }
        }
    }

    @Composable
    private fun HistoryScreen(runs: List<ScanRunEntity>, select: (String) -> Unit, modifier: Modifier) {
        LazyColumn(modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            item { Text("Historial local", style = MaterialTheme.typography.headlineSmall) }
            items(runs, key = { it.runId }) { run ->
                Card(onClick = { select(run.runId) }, modifier = Modifier.fillMaxWidth()) { RunCardContent(run) }
            }
        }
    }

    @Composable
    private fun BacktestScreen(outcomes: List<BacktestOutcomeEntity>, modifier: Modifier) {
        val completed = outcomes.size
        val winners = outcomes.count { it.returnPct > 0 }
        val avg = outcomes.map { it.returnPct }.average().takeIf { !it.isNaN() } ?: 0.0
        LazyColumn(modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            item { Text("Seguimiento de señales", style = MaterialTheme.typography.headlineSmall) }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp)) {
                        Text("Evaluaciones: $completed")
                        Text("Positivas: $winners")
                        Text("Retorno medio observado: ${"%.2f".format(avg)}%")
                        Text("Métrica preliminar: se actualiza al ejecutar nuevos scans.", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            items(outcomes.take(100), key = { it.outcomeId }) { outcome ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp)) {
                        Text("${outcome.ticker} · ${outcome.signal}", fontWeight = FontWeight.Bold)
                        Text("${outcome.sourceClose} → ${outcome.latestClose} · ${outcome.returnPct}%")
                    }
                }
            }
        }
    }

    @Composable
    private fun DiagnosticsScreen(modifier: Modifier) {
        val d = DiagnosticsStore.snapshot(this)
        LazyColumn(modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            item { Text("Diagnóstico operativo", style = MaterialTheme.typography.headlineSmall) }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        DiagnosticLine("Notificaciones", d.notificationsGranted)
                        DiagnosticLine("Alarmas exactas", d.exactAlarmGranted)
                        Text("Próxima alarma: ${formatTime(d.nextTriggerMillis)}")
                        Text("Último inicio automático: ${formatTime(d.lastAutomaticStartMillis)}")
                        Text("Último fin automático: ${formatTime(d.lastAutomaticFinishMillis)}")
                        Text("Estado automático: ${d.lastAutomaticStatus}")
                        if (!d.exactAlarmGranted) {
                            Button(onClick = { startActivity(ScanScheduler.permissionIntent(this@MainActivity)) }) {
                                Text("Habilitar alarma exacta")
                            }
                        }
                    }
                }
            }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp)) {
                        Text("Recomendado para Xiaomi / POCO", fontWeight = FontWeight.Bold)
                        Text("Inicio automático activado · Batería sin restricciones · App fijada en recientes")
                    }
                }
            }
        }
    }

    @Composable
    private fun DiagnosticLine(label: String, ok: Boolean) {
        Text("${if (ok) "✓" else "!"} $label: ${if (ok) "correcto" else "requiere atención"}")
    }

    @Composable
    private fun RunCard(run: ScanRunEntity) {
        Card(Modifier.fillMaxWidth()) { RunCardContent(run) }
    }

    @Composable
    private fun RunCardContent(run: ScanRunEntity) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text("${run.marketDateEt} · ${run.status} · ${run.trustStatus}", fontWeight = FontWeight.Bold)
            Text("Cobertura: ${run.candidateCount} · fallos: ${run.failureCount}")
            Text("${run.source} · cache ${run.cacheHitCount} · reintentos ${run.retryCount} · ${run.durationMs / 1000}s", style = MaterialTheme.typography.bodySmall)
        }
    }

    @Composable
    private fun MacroCard(item: MarketSnapshotEntity) {
        Card(Modifier.fillMaxWidth()) {
            Row(Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(item.label, fontWeight = FontWeight.Bold)
                Text("${item.close} · ${if (item.changePct >= 0) "+" else ""}${item.changePct}%")
            }
        }
    }

    @Composable
    private fun CandidateCard(candidate: CandidateEntity, enrichment: CandidateEnrichmentEntity?) {
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(candidate.ticker, fontWeight = FontWeight.Bold)
                    Text("${signalLabel(candidate.signal)} · ${candidate.score}")
                }
                Text("Cierre ${candidate.close} · RSI ${candidate.rsi14} · RVOL ${candidate.relativeVolume}")
                Text("SMA20 ${candidate.sma20} · SMA50 ${candidate.sma50} · ATR ${candidate.atr14}")
                candidate.entry?.let { Text("Entrada $it · Stop ${candidate.stop} · Objetivo ${candidate.target} · R/R ${candidate.rr}") }
                enrichment?.let {
                    Text("Fundamental: ${it.fundamentalsStatus} · Opciones: ${it.optionsStatus}", fontWeight = FontWeight.Bold)
                    val fundamental = listOfNotNull(
                        it.trailingPe?.let { value -> "P/E $value" },
                        it.priceToSales?.let { value -> "P/Ventas $value" },
                        it.epsTrailing?.let { value -> "EPS $value" },
                        it.revenueGrowthPct?.let { value -> "Ingresos ${value}%" },
                        it.profitMarginPct?.let { value -> "Margen neto ${value}%" },
                        it.debtToEquity?.let { value -> "Deuda/Patr. $value" }
                    )
                    if (fundamental.isNotEmpty()) Text(fundamental.joinToString(" · "), style = MaterialTheme.typography.bodySmall)
                    it.optionsPutCallOi?.let { value ->
                        Text("Put/Call OI $value · Calls ${it.optionsNearCallOi ?: 0} · Puts ${it.optionsNearPutOi ?: 0}", style = MaterialTheme.typography.bodySmall)
                    }
                }
                candidate.reason.split(",").filter { it.isNotBlank() }
                    .forEach { Text("• ${reasonLabel(it)}", style = MaterialTheme.typography.bodySmall) }
            }
        }
    }

    private fun signalLabel(signal: String) = when (signal) {
        "TRIGGER_CONFIRMED" -> "Entrada confirmada"
        "READY_WAIT_TRIGGER" -> "Esperar activación"
        "WATCHLIST" -> "En observación"
        else -> "Evitar"
    }

    private fun reasonLabel(reason: String) = mapOf(
        "price_above_sma20" to "Precio sobre la media de 20 sesiones",
        "sma20_above_sma50" to "Tendencia intermedia alcista",
        "rsi_constructive" to "RSI constructivo",
        "macd_bullish" to "MACD alcista",
        "stochastic_confirmed" to "Estocástico confirmado",
        "volume_confirmation" to "Volumen relativo confirmado",
        "breakout_confirmed" to "Ruptura confirmada con volumen",
        "overextended" to "Precio sobreextendido"
    )[reason] ?: reason.replace("_", " ")

    private fun formatTime(epochMillis: Long): String {
        if (epochMillis <= 0) return "no registrada"
        return DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm z")
            .withZone(ZoneId.of("America/New_York"))
            .format(Instant.ofEpochMilli(epochMillis))
    }
}
