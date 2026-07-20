package com.analista.mobile.data

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

val MIGRATION_15_16 = object : Migration(15, 16) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE IF NOT EXISTS run_dataset_artifacts (
                artifactId TEXT NOT NULL PRIMARY KEY,
                runId TEXT NOT NULL,
                ticker TEXT,
                datasetType TEXT NOT NULL,
                contentHash TEXT NOT NULL,
                relativePath TEXT NOT NULL,
                uncompressedBytes INTEGER NOT NULL,
                compressedBytes INTEGER NOT NULL,
                codecVersion TEXT NOT NULL,
                createdAtUtc INTEGER NOT NULL
            )""".trimIndent()
        )
        db.execSQL("CREATE INDEX IF NOT EXISTS index_run_dataset_artifacts_runId ON run_dataset_artifacts(runId)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_run_dataset_artifacts_datasetType ON run_dataset_artifacts(datasetType)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_run_dataset_artifacts_contentHash ON run_dataset_artifacts(contentHash)")
    }
}
