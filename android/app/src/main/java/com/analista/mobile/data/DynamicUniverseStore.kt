package com.analista.mobile.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

class DynamicUniverseStore(context: Context) {
    data class Member(
        val symbol: String,
        val marketCap: Long,
        val sector: String?,
        val industry: String?
    )

    data class Snapshot(
        val members: List<Member>,
        val source: String,
        val createdAtUtc: Long
    ) {
        val symbols: List<String> get() = members.map { it.symbol }
    }

    private val file = File(context.noBackupFilesDir, "dynamic_universe_v1.json")

    fun save(snapshot: Snapshot) {
        require(snapshot.members.isNotEmpty())
        require(snapshot.source.isNotBlank())
        require(snapshot.createdAtUtc > 0L)
        val members = JSONArray()
        snapshot.members.distinctBy { normalize(it.symbol) }.forEach { member ->
            members.put(
                JSONObject()
                    .put("symbol", normalize(member.symbol))
                    .put("marketCap", member.marketCap)
                    .put("sector", member.sector ?: JSONObject.NULL)
                    .put("industry", member.industry ?: JSONObject.NULL)
            )
        }
        val payload = JSONObject()
            .put("source", snapshot.source)
            .put("createdAtUtc", snapshot.createdAtUtc)
            .put("members", members)
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
        val values = root.optJSONArray("members") ?: return@runCatching null
        val members = buildList {
            for (index in 0 until values.length()) {
                val value = values.optJSONObject(index) ?: continue
                val symbol = normalize(value.optString("symbol"))
                val marketCap = value.optLong("marketCap", 0L)
                if (symbol.isBlank() || marketCap <= 0L) continue
                add(
                    Member(
                        symbol = symbol,
                        marketCap = marketCap,
                        sector = value.optNullableString("sector"),
                        industry = value.optNullableString("industry")
                    )
                )
            }
        }.distinctBy { it.symbol }
        if (members.isEmpty()) return@runCatching null
        Snapshot(members, root.optString("source").ifBlank { "LAST_GOOD_DYNAMIC" }, createdAt)
    }.getOrNull()

    fun clear() = file.delete()

    private fun JSONObject.optNullableString(key: String): String? =
        if (has(key) && !isNull(key)) optString(key).trim().takeIf { it.isNotBlank() } else null

    private fun normalize(symbol: String) = symbol.trim().uppercase().replace('.', '-')

    companion object {
        private const val MAX_AGE_MS = 7L * 24L * 60L * 60L * 1_000L
    }
}
