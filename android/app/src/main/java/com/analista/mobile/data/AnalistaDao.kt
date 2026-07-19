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

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAnalysis(rows: List<CandidateAnalysisEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertTradePlans(rows: List<CandidateTradePlanEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertReproducibilityManifests(rows: List<ReproducibilityManifestEntity>)

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertSignalContracts(rows: List<SignalContractEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertTradeOutcomes(rows: List<TradeOutcomeEntity>)

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

    @Query("SELECT * FROM candidate_analysis WHERE runId = :runId ORDER BY finalTradeScore DESC")
    fun observeAnalysis(runId: String): Flow<List<CandidateAnalysisEntity>>

    @Query("SELECT * FROM candidate_trade_plans WHERE runId = :runId ORDER BY tradeRank ASC")
    fun observeTradePlans(runId: String): Flow<List<CandidateTradePlanEntity>>

    @Query("SELECT * FROM reproducibility_manifests WHERE runId = :runId ORDER BY ticker")
    fun observeReproducibilityManifests(runId: String): Flow<List<ReproducibilityManifestEntity>>

    @Query("SELECT * FROM trade_outcomes ORDER BY evaluatedAtUtc DESC")
    fun observeTradeOutcomes(): Flow<List<TradeOutcomeEntity>>

    @Query("SELECT * FROM signal_contracts ORDER BY decisionTimestampUtc DESC LIMIT :limit")
    suspend fun recentSignalContracts(limit: Int = 500): List<SignalContractEntity>

    @Query("SELECT * FROM scan_runs ORDER BY startedAtUtc DESC LIMIT 1")
    suspend fun latestRun(): ScanRunEntity?

    @Query("SELECT * FROM scan_candidates WHERE runId != :currentRunId ORDER BY id DESC LIMIT 300")
    suspend fun priorCandidates(currentRunId: String): List<CandidateEntity>
}
