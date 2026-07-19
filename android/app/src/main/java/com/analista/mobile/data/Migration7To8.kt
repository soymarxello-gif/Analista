package com.analista.mobile.data

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

val MIGRATION_7_8 = object : Migration(7, 8) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE IF NOT EXISTS reproducibility_manifests (
                manifestId TEXT NOT NULL PRIMARY KEY,
                runId TEXT NOT NULL,
                ticker TEXT NOT NULL,
                barsHash TEXT NOT NULL,
                configurationHash TEXT NOT NULL,
                universeHash TEXT NOT NULL,
                manifestHash TEXT NOT NULL,
                barCount INTEGER NOT NULL,
                firstBarEpochSeconds INTEGER,
                lastBarEpochSeconds INTEGER,
                provider TEXT NOT NULL,
                providerHost TEXT NOT NULL,
                providerStatus TEXT NOT NULL,
                fallbackUsed INTEGER NOT NULL,
                cacheHit INTEGER NOT NULL,
                retrievedAtUtc INTEGER NOT NULL,
                engineVersion TEXT NOT NULL
            )""".trimIndent()
        )
        db.execSQL("CREATE INDEX IF NOT EXISTS index_reproducibility_manifests_runId ON reproducibility_manifests(runId)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_reproducibility_manifests_ticker ON reproducibility_manifests(ticker)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_reproducibility_manifests_manifestHash ON reproducibility_manifests(manifestHash)")
    }
}
