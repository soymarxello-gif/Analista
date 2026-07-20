package com.analista.mobile.data

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

val MIGRATION_12_13 = object : Migration(12, 13) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE IF NOT EXISTS option_assessments (
                assessmentId TEXT NOT NULL PRIMARY KEY,
                runId TEXT NOT NULL,
                ticker TEXT NOT NULL,
                status TEXT NOT NULL,
                coveragePct REAL NOT NULL,
                putCallOiTotal REAL,
                putCallOiNearSpot REAL,
                callWallStrike REAL,
                putWallStrike REAL,
                callWallDistancePct REAL,
                putWallDistancePct REAL,
                oiConcentrationPct REAL,
                volumeToOiRatio REAL,
                ivSkewPutMinusCall REAL,
                gammaStatus TEXT NOT NULL,
                bias TEXT NOT NULL,
                optionsScore REAL NOT NULL,
                institutionalScore REAL NOT NULL,
                contrarianAdjustment REAL NOT NULL,
                conflict TEXT NOT NULL,
                reasons TEXT NOT NULL,
                engineVersion TEXT NOT NULL,
                capturedAtUtc INTEGER NOT NULL
            )""".trimIndent()
        )
        db.execSQL("CREATE INDEX IF NOT EXISTS index_option_assessments_runId ON option_assessments(runId)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_option_assessments_ticker ON option_assessments(ticker)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_option_assessments_status ON option_assessments(status)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_option_assessments_bias ON option_assessments(bias)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_option_assessments_conflict ON option_assessments(conflict)")
    }
}
