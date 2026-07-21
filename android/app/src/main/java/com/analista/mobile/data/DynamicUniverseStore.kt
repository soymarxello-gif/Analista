package com.analista.mobile.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

class DynamicUniverseStore(context: Context) {
    data class Snapshot(
        val symbols: List<String>,
        val source: String,
        val createdAtUtc: Long
    )

    private val file = File(context.noBackupFilesDir, "dynamic_universe_v1.json")

    fun save(snapshot: Snapshot) {
        require(snapshot.symbols.isNotEmpty())
        require(snapshot.source.isNotBlank())
        require(snapshot.createdAtUtc > 0L)
        val payload = JSONObject()
            .put("source", snapshot.source)
            .put("createdAtUtc", snapshot.createdAtUtc)
            .put("symbols", JSONArray(snapshot.symbols.map(::normalize).distinct()))
        val temporary = File(file.parentFile, "${file.name}.tmp")
        temporary.writeText(payload.toString())
        if (!temporary.renameTo(file)) {
            file.writeText(payload.toString())
            temporary.delete()
        }
    }

    fun load(nowUtc: Long = System.currentTimeMillis(), maximumAgeMs: Long = MAX_AGE_MS): Snapshot? = runCatching {
        if (!file.exists()) return@runCatching null
        val root = JSONObject(file.readText())
        val createdAt = root.optLong("createdAtUtc", 0L)
        if (createdAt <= 0L || nowUtc - createdAt !in 0..maximumAgeMs) return@runCatching null
        val values = root.optJSONArray("symbols") ?: return@runCatching null
        val symbols = buildList {
            for (index in 0 until values.length()) {
                values.optString(index).takeIf { it.isNotBlank() }?.let { add(normalize(it)) }
            }
        }.distinct()
        if (symbols.isEmpty()) return@runCatching null
        Snapshot(symbols, root.optString("source").ifBlank { "LAST_GOOD_DYNAMIC" }, createdAt)
    }.getOrNull()

    fun clear() = file.delete()

    private fun normalize(symbol: String) = symbol.trim().uppercase().replace('.', '-')

    companion object {
        private const val MAX_AGE_MS = 7L * 24L * 60L * 60L * 1_000L
    }
}
