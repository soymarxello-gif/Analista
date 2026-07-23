package com.analista.mobile

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.analista.mobile.data.BacktestOutcomeEntity
import com.analista.mobile.data.CandidateEntity
import com.analista.mobile.data.CandidateEnrichmentEntity
import com.analista.mobile.data.CandidateTradePlanEntity
import com.analista.mobile.data.FinalDecisionEntity
import com.analista.mobile.data.MarketSnapshotEntity
import com.analista.mobile.data.ScanRunEntity
import com.analista.mobile.data.TradeOutcomeEntity
import com.analista.mobile.schedule.DiagnosticsStore
import com.analista.mobile.schedule.ScanScheduler
import com.analista.mobile.ui.AnalistaTheme
import com.analista.mobile.ui.MainViewModel
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

class MainActivity : ComponentActivity() {
    private val viewModel: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ScanScheduler.scheduleNext(this)
        setContent { AnalistaTheme { AnalistaApp(viewModel) } }
    }

    @OptIn(ExperimentalMaterial3Api::class)
    @Composable
    private fun AnalistaApp(vm: MainViewModel) {
        val runs by vm.runs.collectAsState()
        val candidates by vm.candidates.collectAsState()
        val macro by vm.macro.collectAsState()
        val enrichment by vm.enrichment.collectAsState()
        val finalDecisions by vm.finalDecisions.collectAsState()
        val tradePlans by vm.tradePlans.collectAsState()
        val outcomes by vm.outcomes.collectAsState()
        val tradeOutcomes by vm.tradeOutcomes.collectAsState()
        val running by vm.running.collectAsState()
        val error by vm.error.collectAsState()
        val universeStatus by vm.universeStatus.collectAsState()
        val universeSource by vm.universeSource.collectAsState()
        val universeCount by vm.universeCount.collectAsState()
        var tab by rememberSaveable { mutableIntStateOf(0) }
        val notificationLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }
        LaunchedEffect(Unit) {
            if (Build.VERSION.SDK_INT >= 33) notificationLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        val labels = listOf("Resumen", "Historial", "Backtest", "Diagnóstico")
        Scaffold(
            topBar = {
                TopAppBar(
                    title = {
                        Column {
                            Text("Analista", fontWeight = FontWeight.Bold)
                            Text("Swing long-only · revisión manual", style = MaterialTheme.typography.labelMedium)
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.background,
                        titleContentColor = MaterialTheme.colorScheme.onBackground
                    )
                )
            },
            bottomBar = {
                NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                    labels.forEachIndexed { index, label ->
                        NavigationBarItem(
                            selected = tab == index,
                            onClick = { tab = index },
                            icon = { Text(listOf("◉", "◷", "↗", "⚙")[index]) },
                            label = { Text(label) }
                        )
                    }
                }
            },
            containerColor = MaterialTheme.colorScheme.background
        ) { padding ->
            when (tab) {
                0 -> SummaryScreen(
                    runs = runs,
                    candidates = candidates,
                    enrichment = enrichment,
                    finalDecisions = finalDecisions,
                    tradePlans = tradePlans,
                    macro = macro,
                    running = running,
                    error = error,
                    universeStatus = universeStatus,
                    universeSource = universeSource,
                    universeCount = universeCount,
                    runNow = vm::runNow,
                    modifier = Modifier.padding(padding)
                )
                1 -> HistoryScreen(runs, vm::selectRun, Modifier.padding(padding))
                2 -> BacktestScreen(tradeOutcomes, outcomes, Modifier.padding(padding))
                else -> DiagnosticsScreen(vm, Modifier.padding(padding))
            }
        }
    }

    @Composable
    private fun SummaryScreen(
        runs: List<ScanRunEntity>,
        candidates: List<CandidateEntity>,
        enrichment: List<CandidateEnrichmentEntity>,
        finalDecisions: List<FinalDecisionEntity>,
        tradePlans: List<CandidateTradePlanEntity>,
        macro: List<MarketSnapshotEntity>,
        running: Boolean,
        error: String?,
        universeStatus: String,
        universeSource: String,
        universeCount: Int,
        runNow: () -> Unit,
        modifier: Modifier
    ) {
        val enrichmentByTicker = enrichment.associateBy { it.ticker }
        val decisionByTicker = finalDecisions.associateBy { it.ticker }
        val planByTicker = tradePlans.associateBy { it.ticker }
        val filters = listOf("Todos", "Accionables", "Esperando", "Observación", "Sin setup", "No elegibles")
        var selectedFilter by rememberSaveable { mutableStateOf("Todos") }
        val ordered = candidates
            .filter { candidate -> selectedFilter == "Todos" || bucket(candidate, decisionByTicker[candidate.ticker]) == selectedFilter }
            .sortedWith(
                compareBy<CandidateEntity> { signalPriority(decisionByTicker[it.ticker]?.finalSignal ?: it.signal) }
                    .thenByDescending { decisionByTicker[it.ticker]?.finalTradeScore ?: it.score }
            )
        val counts = candidates.groupingBy { bucket(it, decisionByTicker[it.ticker]) }.eachCount()

        LazyColumn(
            modifier.fillMaxSize().padding(horizontal = 12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            item {
                ScanHealthCard(
                    latest = runs.firstOrNull(),
                    universeStatus = universeStatus,
                    universeSource = universeSource,
                    universeCount = universeCount,
                    candidateCount = candidates.size,
                    running = running,
                    error = error,
                    runNow = runNow
                )
            }
            if (macro.isNotEmpty()) {
                item {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(macro, key = { it.snapshotId }) { MacroPill(it) }
                    }
                }
            }
            item {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(filters) { filter ->
                        FilterChip(
                            selected = selectedFilter == filter,
                            onClick = { selectedFilter = filter },
                            label = {
                                val count = if (filter == "Todos") candidates.size else counts[filter] ?: 0
                                Text("$filter $count")
                            }
                        )
                    }
                }
            }
            if (ordered.isEmpty()) {
                item {
                    Card(Modifier.fillMaxWidth()) {
                        Text(
                            if (candidates.isEmpty()) "Aún no hay resultados. Ejecuta un scan para construir el universo dinámico."
                            else "No hay símbolos en este grupo.",
                            modifier = Modifier.padding(16.dp)
                        )
                    }
                }
            }
            items(ordered, key = { it.id }) { candidate ->
                CompactCandidateCard(
                    candidate = candidate,
                    enrichment = enrichmentByTicker[candidate.ticker],
                    plan = planByTicker[candidate.ticker],
                    decision = decisionByTicker[candidate.ticker]
                )
            }
            item { Spacer(Modifier.height(8.dp)) }
        }
    }

    @Composable
    private fun ScanHealthCard(
        latest: ScanRunEntity?,
        universeStatus: String,
        universeSource: String,
        universeCount: Int,
        candidateCount: Int,
        running: Boolean,
        error: String?,
        runNow: () -> Unit
    ) {
        Card(
            Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
        ) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Column(Modifier.weight(1f)) {
                        Text("Universo", style = MaterialTheme.typography.labelMedium)
                        Text(
                            if (universeCount > 0) "$universeCount símbolos · $universeStatus" else universeStatus,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            sourceLabel(universeSource),
                            style = MaterialTheme.typography.bodySmall,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                    StatusBadge(latest?.trustStatus ?: "SIN DATOS")
                }
                latest?.let {
                    HorizontalDivider()
                    Text("${it.marketDateEt} · analizados ${it.candidateCount} · fallos ${it.failureCount}")
                    Text(it.source, style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                }
                Text("Resultados visibles: $candidateCount · próxima ejecución ${formatTime(ScanScheduler.nextTrigger(this@MainActivity))}", style = MaterialTheme.typography.bodySmall)
                Button(onClick = runNow, enabled = !running, modifier = Modifier.fillMaxWidth()) {
                    Text(if (running) "Preparando universo y analizando…" else "Ejecutar scan ahora")
                }
                error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
            }
        }
    }

    @Composable
    private fun CompactCandidateCard(
        candidate: CandidateEntity,
        enrichment: CandidateEnrichmentEntity?,
        plan: CandidateTradePlanEntity?,
        decision: FinalDecisionEntity?
    ) {
        var expanded by rememberSaveable(candidate.id) { mutableStateOf(false) }
        val signal = decision?.finalSignal ?: candidate.signal
        val score = decision?.finalTradeScore ?: candidate.score
        Card(
            onClick = { expanded = !expanded },
            modifier = Modifier.fillMaxWidth().animateContentSize(),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
        ) {
            Column(Modifier.padding(horizontal = 12.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Column(Modifier.weight(1f)) {
                        Text(candidate.ticker, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text(
                            "${setupLabel(candidate.setupType)} · ${candidate.close}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    Column(horizontalAlignment = androidx.compose.ui.Alignment.End) {
                        SignalBadge(signal)
                        Text("${"%.1f".format(score)}", fontWeight = FontWeight.Bold)
                    }
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(executionLabel(candidate), style = MaterialTheme.typography.bodySmall)
                    Text(if (expanded) "Ocultar detalle ▲" else "Ver detalle ▼", style = MaterialTheme.typography.labelMedium)
                }
                if (expanded) {
                    HorizontalDivider(Modifier.padding(vertical = 4.dp))
                    decision?.let {
                        DetailLine("Decisión", "${signalLabel(it.preliminarySignal)} → ${signalLabel(it.finalSignal)}")
                        DetailLine("Contrato", if (it.eligibleForContract) "Elegible para revisión manual" else "Bloqueado")
                        DetailLine("Confianza", it.confidence)
                        DetailLine("Contexto (solo advertencia)", "Macro ${it.macroRegime} · Fundamental ${it.fundamentalCoverage} · Opciones/Institucional ${it.institutionalCoverage}")
                    }
                    DetailLine("Técnico", "RSI ${candidate.rsi14} · RVOL ${candidate.relativeVolume} · ATR ${candidate.atr14}")
                    DetailLine("Tendencia", "SMA20 ${candidate.sma20} · SMA50 ${candidate.sma50}")
                    DetailLine("Ejecución", "${candidate.quoteStatus}/${candidate.executionQuoteQuality} · ${actionabilityLabel(candidate.actionabilityAtExecution)}")
                    DetailLine("Trigger", "${candidate.plannedTrigger ?: "—"} · máximo ${candidate.maximumEntry ?: "—"} · spread ${fmt(candidate.spreadPct)}")
                    plan?.let {
                        DetailLine("Plan", if (it.riskPlanValid) "Válido" else "No válido")
                        DetailLine("Niveles", "Entrada ${it.plannedEntry} · Stop ${it.structuralStop} (${it.stopType}) · Objetivo ${it.structuralTarget}")
                        DetailLine("Riesgo", "R/R ${it.structuralRr} · ${it.riskPct}% · ${it.shares} acciones · USD ${"%.2f".format(it.riskBudget)}")
                        DetailLine("Ranking", "Legacy #${it.legacyRank} · shadow #${it.tradeRank} · Δ ${rankDeltaLabel(it.rankDelta)}")
                    }
                    enrichment?.let {
                        DetailLine("Datos", "Fundamental ${it.fundamentalsStatus} · Opciones ${it.optionsStatus}")
                        val fundamental = listOfNotNull(
                            it.trailingPe?.let { value -> "P/E $value" },
                            it.priceToSales?.let { value -> "P/Ventas $value" },
                            it.revenueGrowthPct?.let { value -> "Ingresos $value%" },
                            it.profitMarginPct?.let { value -> "Margen $value%" }
                        )
                        if (fundamental.isNotEmpty()) Text(fundamental.joinToString(" · "), style = MaterialTheme.typography.bodySmall)
                    }
                    val reasons = buildList {
                        decision?.vetoReasons?.split(',')?.filter { it.isNotBlank() }?.let(::addAll)
                        decision?.penaltyReasons?.split(',')?.filter { it.isNotBlank() }?.let(::addAll)
                        if (isEmpty()) addAll(candidate.penaltyReasons.split(',').filter { it.isNotBlank() })
                    }.distinct().take(6)
                    if (reasons.isNotEmpty()) {
                        Text("Motivos", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.labelLarge)
                        reasons.forEach { Text("• ${reasonLabel(it)}", style = MaterialTheme.typography.bodySmall) }
                    }
                    decision?.let {
                        Text("Motor: ${it.decisionVersion}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }

    @Composable
    private fun DetailLine(label: String, value: String) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(label, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodySmall)
            Spacer(Modifier.width(12.dp))
            Text(value, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
        }
    }

    @Composable
    private fun SignalBadge(signal: String) {
        val (background, foreground) = when (signal) {
            "TRIGGER_CONFIRMED" -> Color(0xFF14532D) to Color(0xFFBBF7D0)
            "READY_WAIT_TRIGGER", "READY_FOR_NEXT_SESSION", "LIVE_TRIGGER_PENDING" -> Color(0xFF164E63) to Color(0xFFCFFAFE)
            "WATCHLIST", "SETUP_DISCOVERED" -> Color(0xFF3F3F46) to Color(0xFFE4E4E7)
            "VETO", "HARD_VETO", "DATA_BLOCKED" -> Color(0xFF450A0A) to Color(0xFFFECACA)
            else -> Color(0xFF422006) to Color(0xFFFDE68A)
        }
        Surface(color = background, contentColor = foreground, shape = RoundedCornerShape(999.dp)) {
            Text(signalLabel(signal), modifier = Modifier.padding(horizontal = 9.dp, vertical = 3.dp), style = MaterialTheme.typography.labelSmall)
        }
    }

    @Composable
    private fun StatusBadge(status: String) {
        val normalized = status.uppercase()
        val color = when (normalized) {
            "TRUSTED", "LIVE" -> Color(0xFF166534)
            "DEGRADED", "STALE_FALLBACK" -> Color(0xFF854D0E)
            else -> Color(0xFF7F1D1D)
        }
        Surface(color = color, shape = RoundedCornerShape(999.dp)) {
            Text(normalized, modifier = Modifier.padding(horizontal = 9.dp, vertical = 4.dp), style = MaterialTheme.typography.labelSmall)
        }
    }

    @Composable
    private fun MacroPill(item: MarketSnapshotEntity) {
        Surface(color = MaterialTheme.colorScheme.surfaceVariant, shape = RoundedCornerShape(12.dp)) {
            Row(Modifier.padding(horizontal = 10.dp, vertical = 7.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(item.label, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.labelMedium)
                Text("${item.close} ${signed(item.changePct)}%", style = MaterialTheme.typography.labelMedium)
            }
        }
    }

    @Composable
    private fun HistoryScreen(runs: List<ScanRunEntity>, select: (String) -> Unit, modifier: Modifier) {
        LazyColumn(modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item { Text("Historial local", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
            items(runs, key = { it.runId }) { run ->
                Card(onClick = { select(run.runId) }, modifier = Modifier.fillMaxWidth()) { RunCardContent(run) }
            }
        }
    }

    @Composable
    private fun BacktestScreen(
        tradeOutcomes: List<TradeOutcomeEntity>,
        legacyOutcomes: List<BacktestOutcomeEntity>,
        modifier: Modifier
    ) {
        val triggered = tradeOutcomes.count { it.triggered }
        val targets = tradeOutcomes.count { it.exitReason in setOf("TARGET", "GAP_TARGET") }
        val stops = tradeOutcomes.count { it.exitReason in setOf("STOP", "GAP_STOP") }
        val closed = tradeOutcomes.filter { it.tradeReturnR != null }
        val hitRate = if (closed.isEmpty()) 0.0 else closed.count { (it.tradeReturnR ?: 0.0) > 0.0 } * 100.0 / closed.size
        val expectancy = closed.mapNotNull { it.tradeReturnR }.average().takeIf { !it.isNaN() } ?: 0.0
        val netPnl = closed.mapNotNull { it.netPnl }.sum()
        LazyColumn(modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item { Text("Backtest inmutable", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Contratos ${tradeOutcomes.size} · activados $triggered")
                        Text("Objetivos $targets · stops $stops · hit rate ${"%.1f".format(hitRate)}%")
                        Text("Expectancy ${"%.2f".format(expectancy)}R · P&L neto USD ${"%.2f".format(netPnl)}")
                    }
                }
            }
            items(tradeOutcomes.take(100), key = { it.signalId }) { outcome ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(outcome.ticker, fontWeight = FontWeight.Bold)
                            Text(outcome.status)
                        }
                        Text("${outcome.exitReason} · ${outcome.tradeReturnR?.let { "%.2fR".format(it) } ?: "—"} · ${outcome.holdingSessions} sesiones")
                        Text("MFE ${fmt(outcome.mfePct)} · MAE ${fmt(outcome.maePct)}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            if (legacyOutcomes.isNotEmpty()) item { Text("Seguimiento legacy conservado: ${legacyOutcomes.size}", style = MaterialTheme.typography.bodySmall) }
        }
    }

    @Composable
    private fun DiagnosticsScreen(vm: MainViewModel, modifier: Modifier) {
        val d = DiagnosticsStore.snapshot(this@MainActivity)
        val configured by vm.alpacaConfigured.collectAsState()
        val feed by vm.alpacaFeed.collectAsState()
        val status by vm.alpacaStatus.collectAsState()
        val testing by vm.testingAlpaca.collectAsState()
        val institutionalConfigured by vm.institutionalEngineConfigured.collectAsState()
        val institutionalStatus by vm.institutionalEngineStatus.collectAsState()
        val testingInstitutional by vm.testingInstitutionalEngine.collectAsState()
        val reproducibility by vm.reproducibilitySummary.collectAsState()
        val replay by vm.replayDiagnostics.collectAsState()
        val replayRunning by vm.replayRunning.collectAsState()
        val artifacts by vm.datasetArtifacts.collectAsState()
        val universeStatus by vm.universeStatus.collectAsState()
        val universeSource by vm.universeSource.collectAsState()
        val universeCount by vm.universeCount.collectAsState()
        var apiKey by remember { mutableStateOf("") }
        var secretKey by remember { mutableStateOf("") }
        var institutionalUrl by remember { mutableStateOf("") }
        var institutionalToken by remember { mutableStateOf("") }
        LazyColumn(modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item { Text("Diagnóstico operativo", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Motor institucional", fontWeight = FontWeight.Bold)
                        Text(
                            if (institutionalConfigured) "Conectado · $institutionalStatus" else "No configurado · el fallback local está deshabilitado",
                            style = MaterialTheme.typography.bodySmall
                        )
                        if (!institutionalConfigured) {
                            OutlinedTextField(
                                institutionalUrl,
                                { institutionalUrl = it },
                                label = { Text("URL del servicio (https://…)") },
                                singleLine = true,
                                modifier = Modifier.fillMaxWidth()
                            )
                            OutlinedTextField(
                                institutionalToken,
                                { institutionalToken = it },
                                label = { Text("Bearer token") },
                                singleLine = true,
                                visualTransformation = PasswordVisualTransformation(),
                                modifier = Modifier.fillMaxWidth()
                            )
                            Button(
                                onClick = { vm.saveAndTestInstitutionalEngine(institutionalUrl, institutionalToken) },
                                enabled = !testingInstitutional && institutionalUrl.isNotBlank() && institutionalToken.isNotBlank()
                            ) { Text(if (testingInstitutional) "Probando…" else "Guardar y probar motor") }
                        } else {
                            OutlinedButton(onClick = vm::clearInstitutionalEngine) { Text("Desconectar motor") }
                        }
                    }
                }
            }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        Text("Universo y fuentes", fontWeight = FontWeight.Bold)
                        Text("Estado $universeStatus · símbolos $universeCount")
                        Text(sourceLabel(universeSource), style = MaterialTheme.typography.bodySmall)
                        Text("Alpaca ${if (configured) "configurada" else "sin configurar"} · feed $feed · $status")
                    }
                }
            }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        Text("Automatización", fontWeight = FontWeight.Bold)
                        DiagnosticLine("Notificaciones", d.notificationsGranted)
                        DiagnosticLine("Alarmas exactas", d.exactAlarmGranted)
                        Text("Próxima alarma: ${formatTime(d.nextTriggerMillis)}")
                        Text("Último estado: ${d.lastAutomaticStatus}")
                        if (!d.exactAlarmGranted) {
                            OutlinedButton(onClick = { startActivity(ScanScheduler.permissionIntent(this@MainActivity)) }) {
                                Text("Habilitar alarma exacta")
                            }
                        }
                    }
                }
            }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        Text("Reproducibilidad", fontWeight = FontWeight.Bold)
                        Text("${reproducibility.status} · cobertura ${"%.2f".format(reproducibility.coveragePct)}%")
                        Text("Manifiestos ${reproducibility.manifestCount}/${reproducibility.expectedTickers} · artefactos ${artifacts.size}")
                        Text("Proveedores: ${reproducibility.providers.joinToString().ifBlank { "sin datos" }}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        Text("Replay determinista", fontWeight = FontWeight.Bold)
                        Text("${replay.status} · ${replay.coverageLabel} · ${replay.matchLabel}")
                        DiagnosticLine("Corrida reproducible", replay.trustworthy)
                        replay.reasons.take(4).forEach { Text("• ${reasonLabel(it)}", style = MaterialTheme.typography.bodySmall) }
                        Button(onClick = vm::replaySelected, enabled = !replayRunning) {
                            Text(if (replayRunning) "Reproduciendo…" else "Reproducir corrida")
                        }
                    }
                }
            }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Credenciales Alpaca", fontWeight = FontWeight.Bold)
                        Text("Cifradas con Android Keystore; no se incluyen en reportes ni logs.", style = MaterialTheme.typography.bodySmall)
                        if (!configured) {
                            OutlinedTextField(apiKey, { apiKey = it }, label = { Text("API Key") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                            OutlinedTextField(
                                secretKey,
                                { secretKey = it },
                                label = { Text("Secret Key") },
                                singleLine = true,
                                visualTransformation = PasswordVisualTransformation(),
                                modifier = Modifier.fillMaxWidth()
                            )
                            Button(
                                onClick = { vm.saveAndTestAlpaca(apiKey, secretKey, "iex") },
                                enabled = !testing && apiKey.isNotBlank() && secretKey.isNotBlank()
                            ) { Text(if (testing) "Probando…" else "Guardar y probar Alpaca IEX") }
                        } else {
                            OutlinedButton(onClick = vm::clearAlpaca) { Text("Borrar credenciales Alpaca") }
                        }
                    }
                }
            }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp)) {
                        Text("POCO / HyperOS", fontWeight = FontWeight.Bold)
                        Text("Inicio automático · batería sin restricciones · app fijada en recientes")
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
    private fun RunCardContent(run: ScanRunEntity) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text("${run.marketDateEt} · ${run.status} · ${run.trustStatus}", fontWeight = FontWeight.Bold)
            Text("Cobertura ${run.candidateCount} · fallos ${run.failureCount}")
            Text(run.source, style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }

    private fun bucket(candidate: CandidateEntity, decision: FinalDecisionEntity?): String {
        val signal = decision?.finalSignal ?: candidate.signal
        return when {
            signal == "TRIGGER_CONFIRMED" -> "Accionables"
            signal in setOf("READY_WAIT_TRIGGER", "READY_FOR_NEXT_SESSION", "LIVE_TRIGGER_PENDING") -> "Esperando"
            signal in setOf("WATCHLIST", "SETUP_DISCOVERED") -> "Observación"
            signal in setOf("VETO", "HARD_VETO", "DATA_BLOCKED") -> "No elegibles"
            candidate.setupType == "NO_VALID_SETUP" || signal == "AVOID" -> "Sin setup"
            else -> "Observación"
        }
    }

    private fun signalPriority(signal: String): Int = when (signal) {
        "TRIGGER_CONFIRMED" -> 0
        "READY_WAIT_TRIGGER", "READY_FOR_NEXT_SESSION", "LIVE_TRIGGER_PENDING" -> 1
        "WATCHLIST", "SETUP_DISCOVERED" -> 2
        "AVOID" -> 3
        "VETO", "HARD_VETO", "DATA_BLOCKED" -> 4
        else -> 5
    }

    private fun signalLabel(signal: String) = when (signal) {
        "TRIGGER_CONFIRMED" -> "Confirmado"
        "READY_WAIT_TRIGGER", "LIVE_TRIGGER_PENDING" -> "Esperando trigger"
        "READY_FOR_NEXT_SESSION" -> "Próxima sesión"
        "WATCHLIST", "SETUP_DISCOVERED" -> "Setup descubierto"
        "VETO", "HARD_VETO" -> "No elegible"
        "DATA_BLOCKED" -> "Datos insuficientes"
        else -> "Sin setup"
    }

    private fun setupLabel(setup: String) = when (setup) {
        "BREAKOUT" -> "Breakout"
        "BREAKOUT_RETEST" -> "Retest"
        "PULLBACK_EMA20" -> "Pullback EMA20"
        "PULLBACK_EMA50" -> "Pullback EMA50"
        "SUPPORT_RECLAIM" -> "Reclaim"
        "VOLATILITY_CONTRACTION" -> "Contracción"
        "FAILED_BREAKOUT" -> "Ruptura fallida"
        "NO_VALID_SETUP" -> "Sin setup"
        else -> setup.replace('_', ' ').lowercase().replaceFirstChar { it.uppercase() }
    }

    private fun executionLabel(candidate: CandidateEntity): String = when (candidate.actionabilityAtExecution) {
        "MARKET_CLOSED_ANALYSIS_ONLY" -> "Análisis fuera de sesión"
        "ACTIONABLE_REVIEW" -> "Precio ejecutable validado"
        "WAIT_TRIGGER" -> "Esperando trigger"
        "QUOTE_STALE" -> "Cotización antigua"
        "QUOTE_MISSING" -> "Sin cotización ejecutable"
        "NO_VALID_SETUP" -> "Sin estructura operable"
        "VETOED" -> "No elegible"
        else -> actionabilityLabel(candidate.actionabilityAtExecution)
    }

    private fun actionabilityLabel(value: String) = value.replace('_', ' ').lowercase().replaceFirstChar { it.uppercase() }

    private fun sourceLabel(source: String): String = when (source) {
        "ALPACA_ASSETS+NASDAQ_METADATA+ALPACA_BARS" -> "Alpaca Assets + Nasdaq + barras Alpaca"
        "INSTITUTIONAL_POINT_IN_TIME_API" -> "API institucional · store point-in-time"
        "LAST_GOOD_DYNAMIC" -> "Último universo dinámico válido"
        "EMERGENCY_STATIC" -> "Fallback estático de emergencia"
        "NONE", "" -> "Fuente aún no resuelta"
        else -> source.replace('_', ' ')
    }

    private fun reasonLabel(reason: String) = mapOf(
        "price_below_min" to "Precio inferior al mínimo",
        "market_cap_below_min" to "Capitalización conocida inferior al mínimo",
        "market_cap_unverified" to "Capitalización no verificada",
        "instrument_type_unverified" to "Tipo de instrumento no verificado",
        "eligibility_metadata_unverified" to "Elegibilidad pendiente de validar",
        "market_session_blocks_contract" to "Fuera de sesión ejecutable",
        "market_session_blocks_execution" to "Análisis fuera de sesión",
        "no_valid_setup" to "Sin setup swing válido",
        "failed_breakout" to "Ruptura fallida",
        "overextended" to "Precio sobreextendido",
        "institutional_conflict_high" to "Conflicto institucional alto",
        "risk_plan_invalid" to "Plan de riesgo inválido",
        "base_risk_plan_invalid" to "Plan estructural inválido",
        "quote_stale" to "Cotización antigua",
        "quote_stale_blocks_execution" to "Cotización antigua bloquea ejecución",
        "fundamentals_unavailable" to "Fundamentales no disponibles",
        "options_ratio_missing" to "Cobertura de opciones insuficiente",
        "replay_mismatches_detected" to "El replay detectó discrepancias",
        "missing_replay_datasets" to "Faltan datasets para reproducir",
        "replay_not_executed" to "Replay aún no ejecutado"
    )[reason] ?: reason.replace('_', ' ')

    private fun rankDeltaLabel(delta: Int): String = if (delta > 0) "+$delta" else delta.toString()
    private fun fmt(value: Double?): String = value?.let { "${"%.2f".format(it)}%" } ?: "—"
    private fun signed(value: Double): String = if (value >= 0) "+${"%.2f".format(value)}" else "%.2f".format(value)

    private fun formatTime(epochMillis: Long): String {
        if (epochMillis <= 0) return "no registrada"
        return DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm z")
            .withZone(ZoneId.of("America/New_York"))
            .format(Instant.ofEpochMilli(epochMillis))
    }
}
