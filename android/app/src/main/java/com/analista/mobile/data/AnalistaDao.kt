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
import com.analista.mobile.domain.LiveUniverseSnapshotAssembler
import com.analista.mobile.domain.OptionAssessmentPersistenceFactory
import com.analista.mobile.domain.RankingComparisonPersistenceFactory
import com.analista.mobile.domain.TradePlanGenerationEngine
import kotlinx.coroutines.flow.Flow
import java.time.LocalDate
import java.time.ZoneId

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

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertOptionAssessments(rows: List<OptionAssessmentEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertUniverseSnapshot(row: UniverseSnapshotEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertUniverseMembers(rows: List<UniverseMemberEntity>)

    @Transaction
    suspend fun saveUniverseSnapshot(snapshot: UniverseSnapshotEntity, members: List<UniverseMemberEntity>) {
        require(members.all { it.snapshotId == snapshot.snapshotId })
        insertUniverseSnapshot(snapshot)
        if (members.isNotEmpty()) insertUniverseMembers(members)
    }

    @Transaction
    suspend fun insertEnrichment(rows: List<CandidateEnrichmentEntity>) {
        if (rows.isEmpty()) return
        insertEnrichmentRaw(rows)
        val fundamentalSnapshots = rows.mapNotNull { row ->
            if (row.fundamentalsStatus !in setOf("AVAILABLE_COMPLETE", "AVAILABLE_PARTIAL")) return@mapNotNull null
            val registered = FundamentalSnapshotRegistry.get(row.ticker) ?: return@mapNotNull null
            FundamentalAssessmentEngine.toEntity(
                runId = row.runId,
                ticker = row.ticker,
                metrics = registered.metrics,
                capturedAtUtc = row.capturedAtUtc
            )
        }
        if (fundamentalSnapshots.isNotEmpty()) insertFundamentalSnapshots(fundamentalSnapshots)
        val optionAssessments = rows.mapNotNull { row ->
            val chain = OptionChainRegistry.get(row.ticker) ?: return@mapNotNull null
            OptionAssessmentPersistenceFactory.create(
                runId = row.runId,
                ticker = row.ticker,
                chain = chain,
                capturedAtUtc = row.capturedAtUtc
            )
        }
        if (optionAssessments.isNotEmpty()) insertOptionAssessments(optionAssessments)
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
        val createdAtUtc = System.currentTimeMillis()
        val liveUniverse = LiveUniverseSnapshotAssembler.assemble(
            runId = runId,
            fallbackUniverse = ScanRepository.DEFAULT_TICKERS,
            effectiveDate = LocalDate.now(ZoneId.of("America/New_York")).toString(),
            createdAtUtc = createdAtUtc
        )
        val engineBundleVersion = listOf(
            CanonicalAnalysisEngine.ENGINE_VERSION,
            DecisionOverlayEngine.ENGINE_VERSION,
            TradePlanGenerationEngine.ENGINE_VERSION
        ).joinToString("+")
        val definition = LiveRunDefinitionAssembler.assemble(
            runId = runId,
            universe = liveUniverse.universe,
            manifests = rows,
            engineBundleVersion = engineBundleVersion,
            createdAtUtc = createdAtUtc
        )
        insertReproducibilityBundle(rows, definition)
        saveUniverseSnapshot(liveUniverse.bundle.snapshot, liveUniverse.bundle.members)
        RunUniverseRegistry.remove(runId)
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

    @Query("SELECT * FROM option_assessments WHERE runId = :runId ORDER BY institutionalScore DESC")
    fun observeOptionAssessments(runId: String): Flow<List<OptionAssessmentEntity>>

    @Query("SELECT * FROM universe_snapshots ORDER BY effectiveDate DESC, createdAtUtc DESC LIMIT 1")
    fun observeLatestUniverseSnapshot(): Flow<UniverseSnapshotEntity?>

    @Query("SELECT * FROM universe_members WHERE snapshotId = :snapshotId ORDER BY ticker")
    fun observeUniverseMembers(snapshotId: String): Flow<List<UniverseMemberEntity>>

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
