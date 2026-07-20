package com.analista.mobile.data

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

class RunDatasetStoreTest {
    @Test
    fun barCodecIsStableAcrossInputOrder() {
        val first = PriceBar(1L, 10.0, 11.0, 9.0, 10.5, 100L)
        val second = PriceBar(2L, 10.5, 12.0, 10.0, 11.5, 200L)
        val a = NormalizedDatasetCodec.bars("abc", listOf(second, first))
        val b = NormalizedDatasetCodec.bars("ABC", listOf(first, second))
        assertArrayEquals(a, b)
        assertEquals(NormalizedDatasetCodec.sha256(a), NormalizedDatasetCodec.sha256(b))
    }

    @Test
    fun writesReadsAndDeduplicatesByContentHash() = runTest {
        val root = Files.createTempDirectory("analista-datasets").toFile()
        try {
            val store = RunDatasetStore(root)
            val payload = NormalizedDatasetCodec.bars(
                "TEST",
                listOf(PriceBar(1L, 10.0, 11.0, 9.0, 10.5, 100L))
            )
            val first = store.write("run-1", "normalized_bars", "TEST", payload, 1L)
            val second = store.write("run-2", "normalized_bars", "TEST", payload, 2L)
            assertEquals(first.contentHash, second.contentHash)
            assertEquals(first.relativePath, second.relativePath)
            assertTrue(first.compressedBytes > 0L)
            assertArrayEquals(payload, store.read(first))
            assertTrue(store.verify(second))
        } finally {
            root.deleteRecursively()
        }
    }

    @Test
    fun detectsTamperedArtifact() = runTest {
        val root = Files.createTempDirectory("analista-datasets").toFile()
        try {
            val store = RunDatasetStore(root)
            val payload = "{\"ok\":true}".toByteArray()
            val artifact = store.write("run-1", "macro_snapshot", null, payload, 1L)
            File(root, artifact.relativePath).writeText("tampered")
            assertFalse(store.verify(artifact))
        } finally {
            root.deleteRecursively()
        }
    }
}
