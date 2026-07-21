package com.analista.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.analista.mobile.ui.AnalistaTheme
import com.analista.mobile.ui.MainViewModel
import com.analista.mobile.ui.OfficialSourceUiState
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

class OfficialSourcesActivity : ComponentActivity() {
    private val viewModel: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            AnalistaTheme {
                OfficialSourcesScreen(
                    viewModel = viewModel,
                    close = ::finish
                )
            }
        }
    }
}

@Composable
private fun OfficialSourcesScreen(viewModel: MainViewModel, close: () -> Unit) {
    val state by viewModel.officialSources.collectAsState()
    val refreshing by viewModel.refreshingOfficialSources.collectAsState()
    val error by viewModel.error.collectAsState()
    var fredKey by remember { mutableStateOf("") }
    var secEmail by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Fuentes oficiales") },
                navigationIcon = {
                    OutlinedButton(onClick = close, modifier = Modifier.padding(horizontal = 8.dp)) {
                        Text("Volver")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            SourceHealthCard(state)
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("FRED", fontWeight = FontWeight.Bold)
                    Text(
                        "La clave se cifra con Android Keystore y nunca vuelve a mostrarse.",
                        style = MaterialTheme.typography.bodySmall
                    )
                    Text(if (state.fredConfigured) "Configurado" else "Sin configurar")
                    OutlinedTextField(
                        value = fredKey,
                        onValueChange = { fredKey = it },
                        label = { Text(if (state.fredConfigured) "Nueva API key (opcional)" else "API key FRED") },
                        singleLine = true,
                        visualTransformation = PasswordVisualTransformation(),
                        modifier = Modifier.fillMaxWidth()
                    )
                    if (state.fredConfigured) {
                        OutlinedButton(onClick = viewModel::clearFredApiKey) { Text("Borrar clave FRED") }
                    }
                }
            }
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("SEC EDGAR", fontWeight = FontWeight.Bold)
                    Text(
                        "SEC exige un correo de contacto válido en el User-Agent. Se cifra y no se muestra de nuevo.",
                        style = MaterialTheme.typography.bodySmall
                    )
                    Text(if (state.secConfigured) "Contacto configurado" else "Sin contacto configurado")
                    OutlinedTextField(
                        value = secEmail,
                        onValueChange = { secEmail = it },
                        label = { Text(if (state.secConfigured) "Nuevo correo (opcional)" else "Correo de contacto SEC") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                    if (state.secConfigured) {
                        OutlinedButton(onClick = viewModel::clearSecContactEmail) { Text("Borrar contacto SEC") }
                    }
                }
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = {
                        viewModel.saveAndRefreshOfficialSources(fredKey, secEmail)
                        fredKey = ""
                        secEmail = ""
                    },
                    enabled = !refreshing && (fredKey.isNotBlank() || secEmail.isNotBlank()),
                    modifier = Modifier.weight(1f)
                ) { Text(if (refreshing) "Actualizando…" else "Guardar y actualizar") }
                OutlinedButton(
                    onClick = viewModel::refreshOfficialSources,
                    enabled = !refreshing,
                    modifier = Modifier.weight(1f)
                ) { Text("Probar fuentes") }
            }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Text(
                "Cboe y CFTC no requieren credenciales. Sin FRED o SEC, esos módulos permanecen UNKNOWN y no se interpretan como neutrales.",
                style = MaterialTheme.typography.bodySmall
            )
        }
    }
}

@Composable
private fun SourceHealthCard(state: OfficialSourceUiState) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text("Diagnóstico de cobertura", fontWeight = FontWeight.Bold)
            Text("Estado: ${state.status}")
            Text("FRED: ${state.fredSeriesCount} series · ${if (state.fredConfigured) "configurado" else "sin clave"}")
            Text("Cboe: ${if (state.cboeAvailable) "disponible" else "sin datos"}")
            Text("CFTC: ${state.cftcMarketsCount} mercados")
            Text("SEC: ${state.secTickerCount} tickers · ${if (state.secConfigured) "contacto configurado" else "sin contacto"}")
            state.refreshedAtUtc?.let { Text("Actualizado: ${formatOfficialTime(it)}", style = MaterialTheme.typography.bodySmall) }
        }
    }
}

private fun formatOfficialTime(epochMillis: Long): String = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm z")
    .withZone(ZoneId.of("America/New_York"))
    .format(Instant.ofEpochMilli(epochMillis))
