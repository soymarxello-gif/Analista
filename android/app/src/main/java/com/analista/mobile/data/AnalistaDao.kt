package com.analista.mobile.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

@Dao
interface AnalistaDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertRun(run: ScanRunEntity)
    @Insert
    suspend fun insertCandidates(candidates: List<CandidateEntity>)
    @Transaction
    suspend fun saveRun(run: ScanRunEntity, candidates: List<CandidateEntity>) {
        insertRun(run)
        if (candidates.isNotEmpty()) insertCandidates(candidates)
    }
    @Query("SELECT * FROM scan_runs ORDER BY startedAtUtc DESC")
    fun observeRuns(): Flow<List<ScanRunEntity>>
    @Query("SELECT * FROM scan_candidates WHERE runId = :runId ORDER BY score DESC")
    fun observeCandidates(runId: String): Flow<List<CandidateEntity>>
}
