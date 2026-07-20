package com.analista.mobile.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface ReplayDao {
    @Query("SELECT * FROM scan_runs WHERE runId = :runId LIMIT 1")
    suspend fun getRun(runId: String): ScanRunEntity?

    @Query("SELECT * FROM run_definitions WHERE runId = :runId LIMIT 1")
    suspend fun getRunDefinition(runId: String): RunDefinitionEntity?

    @Query("SELECT * FROM reproducibility_manifests WHERE runId = :runId ORDER BY ticker")
    suspend fun getManifests(runId: String): List<ReproducibilityManifestEntity>

    @Query("SELECT * FROM scan_candidates WHERE runId = :runId ORDER BY ticker")
    suspend fun getCandidates(runId: String): List<CandidateEntity>

    @Query("SELECT * FROM candidate_enrichment WHERE runId = :runId ORDER BY ticker")
    suspend fun getEnrichment(runId: String): List<CandidateEnrichmentEntity>

    @Query("SELECT * FROM candidate_analysis WHERE runId = :runId ORDER BY ticker")
    suspend fun getAnalysis(runId: String): List<CandidateAnalysisEntity>

    @Query("SELECT * FROM candidate_trade_plans WHERE runId = :runId ORDER BY ticker")
    suspend fun getTradePlans(runId: String): List<CandidateTradePlanEntity>

    @Query("SELECT * FROM final_decisions WHERE runId = :runId ORDER BY ticker")
    suspend fun getFinalDecisions(runId: String): List<FinalDecisionEntity>

    @Query("SELECT * FROM run_dataset_artifacts WHERE runId = :runId ORDER BY datasetType, ticker")
    suspend fun getArtifacts(runId: String): List<RunDatasetArtifactEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertReplayResult(result: ReplayResultEntity)

    @Query("SELECT * FROM replay_results WHERE runId = :runId ORDER BY evaluatedAtUtc DESC LIMIT 1")
    fun observeReplayResult(runId: String): Flow<ReplayResultEntity?>
}
