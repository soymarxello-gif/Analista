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

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertOutcomes(outcomes: List<BacktestOutcomeEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertMarketSnapshots(snapshots: List<MarketSnapshotEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertEnrichment(rows: List<CandidateEnrichmentEntity>)

    @Transaction
    suspend fun saveRun(run: ScanRunEntity, candidates: List<CandidateEntity>, snapshots: List<MarketSnapshotEntity>) {
        insertRun(run)
        if (candidates.isNotEmpty()) insertCandidates(candidates)
        if (snapshots.isNotEmpty()) insertMarketSnapshots(snapshots)
    }

    @Query("SELECT * FROM scan_runs ORDER BY startedAtUtc DESC")
    fun observeRuns(): Flow<List<ScanRunEntity>>

    @Query("SELECT * FROM scan_candidates WHERE runId = :runId ORDER BY score DESC")
    fun observeCandidates(runId: String): Flow<List<CandidateEntity>>

    @Query("SELECT * FROM market_snapshots WHERE runId = :runId ORDER BY symbol")
    fun observeMarketSnapshots(runId: String): Flow<List<MarketSnapshotEntity>>

    @Query("SELECT * FROM backtest_outcomes ORDER BY evaluatedAtUtc DESC")
    fun observeOutcomes(): Flow<List<BacktestOutcomeEntity>>

    @Query("SELECT * FROM candidate_enrichment WHERE runId = :runId")
    fun observeEnrichment(runId: String): Flow<List<CandidateEnrichmentEntity>>

    @Query("SELECT * FROM scan_runs ORDER BY startedAtUtc DESC LIMIT 1")
    suspend fun latestRun(): ScanRunEntity?

    @Query("SELECT * FROM scan_candidates WHERE runId != :currentRunId ORDER BY id DESC LIMIT 300")
    suspend fun priorCandidates(currentRunId: String): List<CandidateEntity>
}
