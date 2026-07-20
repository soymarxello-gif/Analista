package com.analista.mobile.data

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.mock
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import java.nio.file.Files

class RunReplayServiceTest {
    @Test
    fun missingStoredRunPersistsInvalidReplayInsteadOfThrowing() = runTest {
        val dao = mock<ReplayDao>()
        whenever(dao.getRun("run-1")).thenReturn(null)
        val root = Files.createTempDirectory("analista-replay-service").toFile()
        try {
            val result = RunReplayService(dao, RunDatasetStore(root)).replay("run-1", 1L)
            assertEquals("INVALID", result.status)
            assertTrue(result.reasons.contains("missing_scan_run"))
            verify(dao).upsertReplayResult(any())
        } finally {
            root.deleteRecursively()
        }
    }
}
