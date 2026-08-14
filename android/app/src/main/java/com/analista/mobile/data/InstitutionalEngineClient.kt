package com.analista.mobile.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.time.ZoneId
import java.util.concurrent.TimeUnit

class InstitutionalEngineClient(
    private val credentials: InstitutionalEngineCredentialsStore,
    private val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.MINUTES)
        .build()
) {
    data class RunResult(
        val run: ScanRunEntity,
        val candidates: List<CandidateEntity>,
        val universeCount: Int,
        val status: String
    )

    suspend fun test(): String = withContext(Dispatchers.IO) {
        val configured = credentials.load() ?: error("Configura la URL del motor institucional")
        val request = request(configured, "/v1/status").get().build()
        http.newCall(request).execute().use { response ->
            check(response.isSuccessful) { "Motor institucional HTTP ${response.code}" }
            val payload = JSONObject(response.body?.string().orEmpty())
            if (payload.getBoolean("operational")) "OPERATIONAL" else "STORE_EMPTY"
        }
    }

    suspend fun runAndPersist(dao: AnalistaDao): RunResult = withContext(Dispatchers.IO) {
        val configured = credentials.load() ?: error(
            "Motor institucional no configurado. El escáner local legacy no se usa como fallback."
        )
        val started = System.currentTimeMillis()
        val request = request(configured, "/v1/runs")
            .post("{}".toRequestBody(JSON))
            .build()
        val payload = http.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            check(response.isSuccessful) { "Motor institucional HTTP ${response.code}: ${body.take(240)}" }
            JSONObject(body)
        }
        val runId = payload.getString("run_id")
        val signals = payload.getJSONArray("signals")
        val candidates = buildList {
            for (index in 0 until signals.length()) {
                val signal = signals.getJSONObject(index)
                val metadata = signal.optJSONObject("metadata") ?: JSONObject()
                val close = metadata.optFinite("close")
                val contextWarnings = metadata.optJSONArray("context_warnings")?.strings().orEmpty()
                val eligibilityWarnings = metadata.optJSONArray("eligibility_warnings")?.strings().orEmpty()
                    .map { warning ->
                        if (warning == "stock_market_cap_unavailable") {
                            "Capitalización no disponible; setup evaluado con datos técnicos"
                        } else warning
                    }
                val reasons = (signal.getJSONArray("reasons").strings() + contextWarnings + eligibilityWarnings)
                    .distinct()
                    .joinToString(",")
                add(
                    CandidateEntity(
                        runId = runId,
                        ticker = signal.getString("symbol"),
                        signal = signal.getString("state"),
                        score = signal.getDouble("setup_quality"),
                        close = close,
                        sma20 = metadata.optFinite("ema20"),
                        sma50 = metadata.optFinite("ema50"),
                        rsi14 = metadata.optFinite("rsi14"),
                        macd = metadata.optFinite("macd"),
                        macdSignal = metadata.optFinite("macd_signal"),
                        stochastic = metadata.optFinite("stochastic14"),
                        atr14 = metadata.optFinite("atr14"),
                        relativeVolume = metadata.optFinite("relative_volume20"),
                        entry = signal.getDouble("trigger_price"),
                        stop = signal.getDouble("stop_price"),
                        target = signal.getDouble("target_price"),
                        rr = 2.0,
                        reason = reasons,
                        quoteStatus = "NOT_REQUESTED",
                        executionQuoteQuality = metadata.optString("feed_grade", "UNKNOWN"),
                        triggerConfirmed = signal.getString("state") == "TRIGGER_CONFIRMED",
                        setupType = signal.getString("setup_type"),
                        penaltyReasons = reasons,
                        actionableEntry = null,
                        actionableStop = null,
                        actionableTarget = null,
                        theoreticalEntry = signal.getDouble("trigger_price"),
                        theoreticalStop = signal.getDouble("stop_price"),
                        theoreticalTarget = signal.getDouble("target_price"),
                        referenceClose = close,
                        plannedTrigger = signal.getDouble("trigger_price"),
                        maximumEntry = signal.getDouble("maximum_entry"),
                        actionabilityAtExecution = signal.getString("state")
                    )
                )
            }
        }
        val startedAt = Instant.parse(payload.getString("started_at")).toEpochMilli()
        val finishedAt = Instant.parse(payload.getString("finished_at")).toEpochMilli()
        val run = ScanRunEntity(
            runId = runId,
            startedAtUtc = startedAt,
            finishedAtUtc = finishedAt,
            marketDateEt = Instant.ofEpochMilli(startedAt).atZone(ZoneId.of("America/New_York")).toLocalDate().toString(),
            status = payload.getString("status"),
            trustStatus = if (payload.getString("status").startsWith("COMPLETED")) "INSTITUTIONAL_STORE" else "DATA_BLOCKED",
            candidateCount = candidates.size,
            failureCount = payload.getJSONArray("errors").length(),
            source = "Institutional API · point-in-time store",
            durationMs = (finishedAt - startedAt).coerceAtLeast(System.currentTimeMillis() - started)
        )
        dao.saveRun(run, candidates, emptyList())
        RunResult(run, candidates, payload.getInt("universe_count"), payload.getString("status"))
    }

    private fun request(value: InstitutionalEngineCredentialsStore.Credentials, path: String): Request.Builder {
        return Request.Builder().url(value.baseUrl + path).apply {
            if (value.bearerToken.isNotBlank()) header("Authorization", "Bearer ${value.bearerToken}")
        }
    }

    private fun JSONObject.optFinite(name: String): Double {
        val value = optDouble(name, Double.NaN)
        return if (value.isFinite()) value else Double.NaN
    }

    private fun JSONArray.strings(): List<String> = buildList {
        for (index in 0 until length()) add(optString(index))
    }

    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()
    }
}
