package com.analista.mobile.data

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

val MIGRATION_16_17 = object : Migration(16, 17) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE IF NOT EXISTS replay_results (
                replayId TEXT NOT NULL PRIMARY KEY,
                runId TEXT NOT NULL,
                status TEXT NOT NULL,
                expectedTickers INTEGER NOT NULL,
                replayedTickers INTEGER NOT NULL,
                fullyMatchedTickers INTEGER NOT NULL,
                mismatchedTickers INTEGER NOT NULL,
                missingDatasetCount INTEGER NOT NULL,
                reasons TEXT NOT NULL,
                tickerDetails TEXT NOT NULL,
                engineVersion TEXT NOT NULL,
                evaluatedAtUtc INTEGER NOT NULL
            )""".trimIndent()
        )
        db.execSQL("CREATE INDEX IF NOT EXISTS index_replay_results_runId ON replay_results(runId)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_replay_results_status ON replay_results(status)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_replay_results_evaluatedAtUtc ON replay_results(evaluatedAtUtc)")
    }
}
