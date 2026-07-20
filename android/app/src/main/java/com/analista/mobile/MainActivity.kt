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
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
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
        val finalDecisions by vm.finalDecisions.collectAsState()
        val tradePlans by vm.tradePlans.collectAsState()
        val outcomes by vm.outcomes.collectAsState()
        val tradeOutcomes by vm.tradeOutcomes.collectAsState()
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
                0 -> SummaryScreen(
                    runs = runs,
                    candidates = candidates,
                    enrichment = enrichment,
                    finalDecisions = finalDecisions,
                    tradePlans = tradePlans,
                    macro = macro,
                    running = running,
                    error = error,
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
        runNow: () -> Unit,
        modifier: Modifier
    ) {
        LazyColumn(modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Ejecución local autónoma", fontWeight = FontWeight.Bold)
                        Text("NYSE · 09:20 America/New_York · Alpaca/Yahoo")
                        Text("Próxima ejecución: ${formatTime(ScanScheduler.nextTrigger(this@MainActivity))}")
                        Button(onClick = runNow, enabled = !running) {
                            Text(if (running) "Ejecutando y verificando…" else "Ejecutar ahora")
                        }
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
            val decisionByTicker = finalDecisions.associateBy { it.ticker }
            val planByTicker = tradePlans.associateBy { it.ticker }
            items(candidates, key = { it.id }) { candidate ->
                CandidateCard(
                    candidate = candidate,
                    enrichment = enrichmentByTicker[candidate.ticker],
                    plan = planByTicker[candidate.ticker],
                    decision = decisionByTicker[candidate.ticker]
                )
            }
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
    private fun BacktestScreen(
        tradeOutcomes: List<TradeOutcomeEntity>,
        legacyOutcomes: List<BacktestOutcomeEntity>,
        modifier: Modifier
    ) {
        val triggered = tradeOutcomes.count { it.triggered }
        val targets = tradeOutcomes.count { it.exitReason in setOf("TARGET", "GAP_TARGET") }
        val stops = tradeOutcomes.count { it.exitReason in setOf("STOP", "GAP_STOP") }
        val expired = tradeOutcomes.count { it.exitReason == "EXPIRED" }
        val ambiguous = tradeOutcomes.count { it.ambiguousSameBar }
        val closed = tradeOutcomes.filter { it.tradeReturnR != null }
        val hitRate = if (closed.isEmpty()) 0.0 else closed.count { (it.tradeReturnR ?: 0.0) > 0.0 } * 100.0 / closed.size
        val expectancy = closed.mapNotNull { it.tradeReturnR }.average().takeIf { !it.isNaN() } ?: 0.0
        val netPnl = closed.mapNotNull { it.netPnl }.sum()
        val avgMfe = tradeOutcomes.mapNotNull { it.mfePct }.average().takeIf { !it.isNaN() } ?: 0.0
        val avgMae = tradeOutcomes.mapNotNull { it.maePct }.average().takeIf { !it.isNaN() } ?: 0.0
        LazyColumn(modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            item { Text("Backtest inmutable", style = MaterialTheme.typography.headlineSmall) }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                        Text("Contratos evaluados: ${tradeOutcomes.size}")
                        Text("Activados: $triggered · objetivos: $targets · stops: $stops · expirados: $expired")
                        Text("Hit rate: ${"%.1f".format(hitRate)}% · expectancy ${"%.2f".format(expectancy)}R")
                        Text("P&L neto registrado: $${"%.2f".format(netPnl)}")
                        Text("MFE medio: ${"%.2f".format(avgMfe)}% · MAE medio: ${"%.2f".format(avgMae)}%")
                        if (ambiguous > 0) Text("Resultados ambiguos sin secuencia intradía: $ambiguous")
                        Text("Gaps, slippage y costes se aplican al fill; los markouts permanecen separados.", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            if (tradeOutcomes.isEmpty()) item { Text("Aún no hay contratos con barras posteriores suficientes.") }
            items(tradeOutcomes.take(100), key = { it.signalId }) { outcome ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                        Text("${outcome.ticker} · ${outcome.status}", fontWeight = FontWeight.Bold)
                        Text("Trigger: ${if (outcome.triggered) "sí" else "no"} · salida: ${outcome.exitReason}")
                        Text("Entrada ${outcome.entryFill ?: "—"} · salida ${outcome.exitFill ?: "—"} · sesiones ${outcome.holdingSessions}")
                        Text("Resultado ${fmt(outcome.tradeReturnPct)} · ${outcome.tradeReturnR?.let { "%.2fR".format(it) } ?: "—"}")
                        if (outcome.netPnl != null) {
                            Text("P&L bruto $${"%.2f".format(outcome.grossPnl)} · costes $${"%.2f".format(outcome.totalCosts)} · neto $${"%.2f".format(outcome.netPnl)}")
                        }
                        Text("1D ${fmt(outcome.return1dPct)} · 5D ${fmt(outcome.return5dPct)} · 20D ${fmt(outcome.return20dPct)}")
                        Text("MFE ${fmt(outcome.mfePct)} · MAE ${fmt(outcome.maePct)} · ${outcome.costModelVersion}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            if (legacyOutcomes.isNotEmpty()) item {
                Text("Seguimiento legacy conservado: ${legacyOutcomes.size}", style = MaterialTheme.typography.bodySmall)
            }
        }
    }

    @Composable
    private fun DiagnosticsScreen(vm: MainViewModel, modifier: Modifier) {
        val d = DiagnosticsStore.snapshot(this)
        val configured by vm.alpacaConfigured.collectAsState()
        val feed by vm.alpacaFeed.collectAsState()
        val status by vm.alpacaStatus.collectAsState()
        val testing by vm.testingAlpaca.collectAsState()
        val reproducibility by vm.reproducibilitySummary.collectAsState()
        val replay by vm.replayDiagnostics.collectAsState()
        val replayRunning by vm.replayRunning.collectAsState()
        val artifacts by vm.datasetArtifacts.collectAsState()
        var apiKey by remember { mutableStateOf("") }
        var secretKey by remember { mutableStateOf("") }
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
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Reproducibilidad del scan", fontWeight = FontWeight.Bold)
                        Text("Estado: ${reproducibility.status} · cobertura ${"%.2f".format(reproducibility.coveragePct)}%")
                        Text("Manifiestos: ${reproducibility.manifestCount}/${reproducibility.expectedTickers}")
                        Text("Configuraciones: ${reproducibility.uniqueConfigurationHashes} · universos: ${reproducibility.uniqueUniverseHashes}")
                        Text("Proveedores: ${reproducibility.providers.joinToString().ifBlank { "sin datos" }}")
                        Text("Fallbacks: ${reproducibility.fallbackCount} · cache: ${reproducibility.cacheHitCount} · inválidos: ${reproducibility.invalidManifestCount}")
                        Text("Artefactos normalizados: ${artifacts.size} · tipos ${artifacts.map { it.datasetType }.distinct().size}")
                    }
                }
            }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        Text("Replay determinista", fontWeight = FontWeight.Bold)
                        Text("Estado: ${replay.status} · cobertura ${replay.coverageLabel}")
                        Text("Coincidencias completas: ${replay.matchLabel} · discrepancias: ${replay.mismatchLabel} · faltantes: ${replay.missingLabel}")
                        DiagnosticLine("Corrida reproducible", replay.trustworthy)
                        replay.reasons.take(5).forEach { Text("• ${reasonLabel(it)}", style = MaterialTheme.typography.bodySmall) }
                        Button(onClick = vm::replaySelected, enabled = !replayRunning) {
                            Text(if (replayRunning) "Reproduciendo…" else "Reproducir corrida seleccionada")
                        }
                    }
                }
            }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Fuente Alpaca", fontWeight = FontWeight.Bold)
                        Text("Configurada: ${if (configured) "sí" else "no"} · feed $feed · estado $status")
                        Text("Las claves se cifran con Android Keystore y no se incluyen en reportes ni logs.", style = MaterialTheme.typography.bodySmall)
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
                            Button(onClick = vm::clearAlpaca) { Text("Borrar credenciales Alpaca") }
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
    private fun CandidateCard(
        candidate: CandidateEntity,
        enrichment: CandidateEnrichmentEntity?,
        plan: CandidateTradePlanEntity?,
        decision: FinalDecisionEntity?
    ) {
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(candidate.ticker, fontWeight = FontWeight.Bold)
                    Text("${signalLabel(decision?.finalSignal ?: candidate.signal)} · ${decision?.finalTradeScore ?: candidate.score}")
                }
                decision?.let {
                    Text("Técnica: ${signalLabel(it.preliminarySignal)} · Final: ${signalLabel(it.finalSignal)}", fontWeight = FontWeight.Bold)
                    Text("Contrato: ${if (it.eligibleForContract) "elegible para revisión manual" else "bloqueado"} · confianza ${it.confidence}")
                    Text("Macro ${it.macroRegime} · Fundamental ${it.fundamentalCoverage} · Institucional ${it.institutionalCoverage}")
                    Text("Frescura de ejecución: ${it.executionFreshness} · motor ${it.decisionVersion}", style = MaterialTheme.typography.bodySmall)
                    it.vetoReasons.split(',').filter { reason -> reason.isNotBlank() }.take(3)
                        .forEach { reason -> Text("Veto: ${reasonLabel(reason)}", style = MaterialTheme.typography.bodySmall) }
                    it.penaltyReasons.split(',').filter { reason -> reason.isNotBlank() }.take(4)
                        .forEach { reason -> Text("Penalización: ${reasonLabel(reason)}", style = MaterialTheme.typography.bodySmall) }
                } ?: Text("Decisión final aún no disponible.", style = MaterialTheme.typography.bodySmall)
                Text("Cierre ${candidate.close} · RSI ${candidate.rsi14} · RVOL ${candidate.relativeVolume}")
                Text("SMA20 ${candidate.sma20} · SMA50 ${candidate.sma50} · ATR ${candidate.atr14}")
                Text("Quote ${candidate.quoteStatus}/${candidate.executionQuoteQuality} · acción ${candidate.actionabilityAtExecution}")
                Text("Trigger ${candidate.plannedTrigger ?: "—"} · máximo ${candidate.maximumEntry ?: "—"} · spread ${fmt(candidate.spreadPct)}")
                plan?.let {
                    Text("Plan estructural ${if (it.riskPlanValid) "válido" else "no válido"}", fontWeight = FontWeight.Bold)
                    Text("Entrada ${it.plannedEntry} · Stop ${it.structuralStop} (${it.stopType}) · Objetivo ${it.structuralTarget}")
                    Text("R/R ${it.structuralRr} · Riesgo ${it.riskPct}% · Recompensa ${it.rewardPct}%")
                    Text("Sizing ${it.shares} acciones · Posición $${"%.2f".format(it.positionValue)} · Riesgo $${"%.2f".format(it.riskBudget)}")
                    Text("Estructura ${it.structureScore} · RS SPY ${it.relativeStrengthStatus} (${it.relativeStrengthScore})")
                    Text("Ranking legacy #${it.legacyRank} · shadow #${it.tradeRank} · Δ ${rankDeltaLabel(it.rankDelta)}")
                    Text("Score operativo auditado ${it.auditedTradeScore}", style = MaterialTheme.typography.bodySmall)
                } ?: Text("Plan operativo aún no disponible.", style = MaterialTheme.typography.bodySmall)
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
                candidate.reason.split(',').filter { it.isNotBlank() }.take(6)
                    .forEach { Text("• ${reasonLabel(it)}", style = MaterialTheme.typography.bodySmall) }
            }
        }
    }

    private fun rankDeltaLabel(delta: Int): String = if (delta > 0) "+$delta" else delta.toString()

    private fun signalLabel(signal: String) = when (signal) {
        "TRIGGER_CONFIRMED" -> "Trigger confirmado"
        "READY_WAIT_TRIGGER" -> "Esperar activación"
        "WATCHLIST" -> "En observación"
        "VETO" -> "Vetado"
        else -> "Evitar"
    }

    private fun reasonLabel(reason: String) = mapOf(
        "price_above_sma20" to "Precio sobre la media de 20 sesiones",
        "sma20_above_sma50" to "Tendencia intermedia alcista",
        "rsi_constructive" to "RSI constructivo",
        "macd_bullish" to "MACD alcista",
        "stochastic_confirmed" to "Estocástico confirmado",
        "volume_confirmation" to "Volumen relativo confirmado",
        "live_trigger_confirmed" to "Trigger actual confirmado",
        "failed_breakout" to "Ruptura fallida",
        "overextended" to "Precio sobreextendido",
        "institutional_conflict_high" to "Conflicto institucional alto",
        "risk_plan_invalid" to "Plan de riesgo inválido",
        "replay_mismatches_detected" to "El replay detectó discrepancias",
        "missing_replay_datasets" to "Faltan datasets para reproducir",
        "replay_not_executed" to "Replay aún no ejecutado"
    )[reason] ?: reason.replace("_", " ")

    private fun fmt(value: Double?): String = value?.let { "${"%.2f".format(it)}%" } ?: "—"

    private fun formatTime(epochMillis: Long): String {
        if (epochMillis <= 0) return "no registrada"
        return DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm z")
            .withZone(ZoneId.of("America/New_York"))
            .format(Instant.ofEpochMilli(epochMillis))
    }
}
