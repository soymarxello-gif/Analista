package com.analista.mobile.data

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

val MIGRATION_9_10 = object : Migration(9, 10) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL(
            """
            CREATE TABLE IF NOT EXISTS `run_definitions` (
                `definitionId` TEXT NOT NULL,
                `runId` TEXT NOT NULL,
                `universeName` TEXT NOT NULL,
                `universeVersion` TEXT NOT NULL,
                `universeSymbolsCsv` TEXT NOT NULL,
                `universeHash` TEXT NOT NULL,
                `configurationVersion` TEXT NOT NULL,
                `configurationJson` TEXT NOT NULL,
                `configurationHash` TEXT NOT NULL,
                `engineBundleVersion` TEXT NOT NULL,
                `createdAtUtc` INTEGER NOT NULL,
                PRIMARY KEY(`definitionId`)
            )
            """.trimIndent()
        )
        db.execSQL("CREATE INDEX IF NOT EXISTS `index_run_definitions_runId` ON `run_definitions` (`runId`)")
        db.execSQL("CREATE INDEX IF NOT EXISTS `index_run_definitions_universeVersion` ON `run_definitions` (`universeVersion`)")
        db.execSQL("CREATE INDEX IF NOT EXISTS `index_run_definitions_configurationVersion` ON `run_definitions` (`configurationVersion`)")
    }
}
