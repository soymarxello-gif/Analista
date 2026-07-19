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
        TradeOutcomeEntity::class
    ],
    version = 6,
    exportSchema = true
)
abstract class AnalistaDatabase : RoomDatabase() {
    abstract fun dao(): AnalistaDao
}
