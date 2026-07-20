package com.analista.mobile.data

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(
    entities = [
        ScanRunEntity::class,
        CandidateEntity::class,
        BacktestOutcomeEntity::class,
        MarketSnapshotEntity::class,
        CandidateEnrichmentEntity::class,
        CandidateAnalysisEntity::class,
        SignalContractEntity::class,
        TradeOutcomeEntity::class,
        CandidateTradePlanEntity::class,
        ReproducibilityManifestEntity::class,
        RankingComparisonEntity::class,
        RunDefinitionEntity::class,
        FinalDecisionEntity::class,
        FundamentalSnapshotEntity::class,
        OptionAssessmentEntity::class
    ],
    version = 13,
    exportSchema = true
)
abstract class AnalistaDatabase : RoomDatabase() {
    abstract fun dao(): AnalistaDao
}
