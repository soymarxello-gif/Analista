package com.analista.mobile.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import com.analista.mobile.domain.CanonicalAnalysisEngine
import com.analista.mobile.domain.DecisionOverlayEngine
import com.analista.mobile.domain.FundamentalAssessmentEngine
import com.analista.mobile.domain.LiveRunDefinitionAssembler
import com.analista.mobile.domain.RankingComparisonPersistenceFactory
import com.analista.mobile.domain.TradePlanGenerationEngine
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
    suspend fun insertEnrichmentRaw(rows: List<CandidateEnrichmentEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertFundamentalSnapshots(rows: List<FundamentalSnapshotEntity>)

    @Transaction
    suspend fun insertEnrichment(rows: List<CandidateEnrichmentEntity>) {
        if (rows.isEmpty()) return
        insertEnrichmentRaw(rows)
        val snapshots = rows.mapNotNull { row ->
            if (row.fundamentalsStatus !in setOf("AVAILABLE_COMPLETE", "AVAILABLE_PARTIAL")) return@mapNotNull null
            val registered = FundamentalSnapshotRegistry.get(row.ticker) ?: return@mapNotNull null
            FundamentalAssessmentEngine.toEntity(
                runId = row.runId,
                ticker = row.ticker,
                metrics = registered.metrics,
                capturedAtUtc = row.capturedAtUtc
            )
        }
        if (snapshots.isNotEmpty()) insertFundamentalSnapshots(snapshots)
    }

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAnalysis(rows: List<CandidateAnalysisEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertFinalDecisions(rows: List<FinalDecisionEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertTradePlansRaw(rows: List<CandidateTradePlanEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertRankingComparison(row: RankingComparisonEntity)

    @Transaction
    suspend fun insertTradePlans(rows: List<CandidateTradePlanEntity>) {
        if (rows.isEmpty()) return
        insertTradePlansRaw(rows)
        RankingComparisonPersistenceFactory.create(rows, System.currentTimeMillis())
            ?.let { insertRankingComparison(it) }
    }

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertReproducibilityManifestsRaw(rows: List<ReproducibilityManifestEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertRunDefinition(row: RunDefinitionEntity)

    @Transaction
    suspend fun insertReproducibilityManifests(rows: List<ReproducibilityManifestEntity>) {
        if (rows.isEmpty()) return
        val runId = rows.first().runId
        require(rows.all { it.runId == runId })
        val engineBundleVersion = listOf(
            CanonicalAnalysisEngine.ENGINE_VERSION,
            DecisionOverlayEngine.ENGINE_VERSION,
            TradePlanGenerationEngine.ENGINE_VERSION
        ).joinToString("+")
        val definition = LiveRunDefinitionAssembler.assemble(
            runId = runId,
            universe = ScanRepository.DEFAULT_TICKERS,
            manifests = rows,
            engineBundleVersion = engineBundleVersion,
            createdAtUtc = System.currentTimeMillis()
        )
        insertReproducibilityBundle(rows, definition)
    }

    @Transaction
    suspend fun insertReproducibilityBundle(
        manifests: List<ReproducibilityManifestEntity>,
        definition: RunDefinitionEntity
    ) {
        require(manifests.isNotEmpty())
        require(manifests.all { it.runId == definition.runId })
        insertReproducibilityManifestsRaw(manifests)
        insertRunDefinition(definition)
    }

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

    @Query("SELECT * FROM fundamental_snapshots WHERE runId = :runId ORDER BY fundamentalScore DESC")
    fun observeFundamentalSnapshots(runId: String): Flow<List<FundamentalSnapshotEntity>>

    @Query("SELECT * FROM candidate_analysis WHERE runId = :runId ORDER BY finalTradeScore DESC")
    fun observeAnalysis(runId: String): Flow<List<CandidateAnalysisEntity>>

    @Query("SELECT * FROM final_decisions WHERE runId = :runId ORDER BY finalTradeScore DESC")
    fun observeFinalDecisions(runId: String): Flow<List<FinalDecisionEntity>>

    @Query("SELECT * FROM candidate_trade_plans WHERE runId = :runId ORDER BY tradeRank ASC")
    fun observeTradePlans(runId: String): Flow<List<CandidateTradePlanEntity>>

    @Query("SELECT * FROM ranking_comparisons WHERE runId = :runId LIMIT 1")
    fun observeRankingComparison(runId: String): Flow<RankingComparisonEntity?>

    @Query("SELECT * FROM reproducibility_manifests WHERE runId = :runId ORDER BY ticker")
    fun observeReproducibilityManifests(runId: String): Flow<List<ReproducibilityManifestEntity>>

    @Query("SELECT * FROM run_definitions WHERE runId = :runId LIMIT 1")
    fun observeRunDefinition(runId: String): Flow<RunDefinitionEntity?>

    @Query("SELECT * FROM trade_outcomes ORDER BY evaluatedAtUtc DESC")
    fun observeTradeOutcomes(): Flow<List<TradeOutcomeEntity>>

    @Query("SELECT * FROM signal_contracts ORDER BY decisionTimestampUtc DESC LIMIT :limit")
    suspend fun recentSignalContracts(limit: Int = 500): List<SignalContractEntity>

    @Query("SELECT * FROM scan_runs ORDER BY startedAtUtc DESC LIMIT 1")
    suspend fun latestRun(): ScanRunEntity?

    @Query("SELECT * FROM scan_candidates WHERE runId != :currentRunId ORDER BY id DESC LIMIT 300")
    suspend fun priorCandidates(currentRunId: String): List<CandidateEntity>
}
