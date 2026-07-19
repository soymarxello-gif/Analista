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
        RunDefinitionEntity::class
    ],
    version = 10,
    exportSchema = true
)
abstract class AnalistaDatabase : RoomDatabase() {
    abstract fun dao(): AnalistaDao
}
