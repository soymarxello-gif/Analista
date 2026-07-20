package com.analista.mobile.data

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException
import java.util.zip.GZIPInputStream
import java.util.zip.GZIPOutputStream

class RunDatasetStore(private val rootDir: File) {
    constructor(context: Context) : this(File(context.filesDir, "run-datasets"))

    suspend fun write(
        runId: String,
        datasetType: String,
        ticker: String?,
        payload: ByteArray,
        createdAtUtc: Long = System.currentTimeMillis()
    ): RunDatasetArtifactEntity = withContext(Dispatchers.IO) {
        val normalizedRunId = runId.trim()
        val normalizedType = datasetType.trim().uppercase()
        val normalizedTicker = ticker?.trim()?.uppercase()?.replace(".", "-")?.takeIf { it.isNotBlank() }
        require(normalizedRunId.isNotBlank())
        require(normalizedType.matches(Regex("[A-Z0-9_]+")))
        require(payload.isNotEmpty())
        require(createdAtUtc > 0L)

        val hash = NormalizedDatasetCodec.sha256(payload)
        val folder = File(rootDir, hash.take(2)).apply { mkdirs() }
        val target = File(folder, "$hash.json.gz")
        if (!target.exists()) {
            val temporary = File(folder, "$hash.${System.nanoTime()}.tmp")
            try {
                GZIPOutputStream(FileOutputStream(temporary)).use { it.write(payload) }
                if (!temporary.renameTo(target)) {
                    temporary.copyTo(target, overwrite = false)
                    temporary.delete()
                }
            } finally {
                if (temporary.exists()) temporary.delete()
            }
        }
        val relative = target.relativeTo(rootDir).invariantSeparatorsPath
        RunDatasetArtifactEntity(
            artifactId = listOf(normalizedRunId, normalizedType, normalizedTicker ?: "ALL", hash).joinToString("|"),
            runId = normalizedRunId,
            ticker = normalizedTicker,
            datasetType = normalizedType,
            contentHash = hash,
            relativePath = relative,
            uncompressedBytes = payload.size.toLong(),
            compressedBytes = target.length(),
            codecVersion = NormalizedDatasetCodec.VERSION,
            createdAtUtc = createdAtUtc
        )
    }

    suspend fun read(artifact: RunDatasetArtifactEntity): ByteArray = withContext(Dispatchers.IO) {
        val root = rootDir.canonicalFile
        val file = File(rootDir, artifact.relativePath).canonicalFile
        if (!file.path.startsWith(root.path + File.separator)) throw IOException("Dataset path escapes store root")
        if (!file.isFile) throw IOException("Dataset artifact missing: ${artifact.relativePath}")
        val output = ByteArrayOutputStream()
        GZIPInputStream(FileInputStream(file)).use { input -> input.copyTo(output) }
        val payload = output.toByteArray()
        if (payload.size.toLong() != artifact.uncompressedBytes) throw IOException("Dataset size mismatch")
        if (NormalizedDatasetCodec.sha256(payload) != artifact.contentHash) throw IOException("Dataset hash mismatch")
        payload
    }

    suspend fun verify(artifact: RunDatasetArtifactEntity): Boolean = runCatching { read(artifact) }.isSuccess
}
