package com.analista.mobile.data

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

val MIGRATION_8_9 = object : Migration(8, 9) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE IF NOT EXISTS ranking_comparisons (
                comparisonId TEXT NOT NULL PRIMARY KEY,
                runId TEXT NOT NULL,
                totalItems INTEGER NOT NULL,
                comparableItems INTEGER NOT NULL,
                missingItems INTEGER NOT NULL,
                topK INTEGER NOT NULL,
                topKOverlapCount INTEGER NOT NULL,
                topKOverlapPct REAL NOT NULL,
                medianAbsoluteDisplacement REAL,
                spearman REAL,
                thresholdsPassed INTEGER NOT NULL,
                status TEXT NOT NULL,
                reasons TEXT NOT NULL,
                engineVersion TEXT NOT NULL,
                calculatedAtUtc INTEGER NOT NULL
            )""".trimIndent()
        )
        db.execSQL("CREATE INDEX IF NOT EXISTS index_ranking_comparisons_runId ON ranking_comparisons(runId)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_ranking_comparisons_status ON ranking_comparisons(status)")
    }
}
