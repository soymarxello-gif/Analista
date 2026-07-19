package com.analista.mobile.data

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

val MIGRATION_10_11 = object : Migration(10, 11) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE IF NOT EXISTS final_decisions (
                decisionId TEXT NOT NULL PRIMARY KEY,
                runId TEXT NOT NULL,
                ticker TEXT NOT NULL,
                preliminarySignal TEXT NOT NULL,
                finalSignal TEXT NOT NULL,
                finalTradeScore REAL NOT NULL,
                eligibleForContract INTEGER NOT NULL,
                confidence TEXT NOT NULL,
                vetoReasons TEXT NOT NULL,
                penaltyReasons TEXT NOT NULL,
                macroRegime TEXT NOT NULL,
                fundamentalCoverage TEXT NOT NULL,
                institutionalCoverage TEXT NOT NULL,
                executionFreshness TEXT NOT NULL,
                decisionVersion TEXT NOT NULL,
                calculatedAtUtc INTEGER NOT NULL
            )""".trimIndent()
        )
        db.execSQL("CREATE INDEX IF NOT EXISTS index_final_decisions_runId ON final_decisions(runId)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_final_decisions_ticker ON final_decisions(ticker)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_final_decisions_finalSignal ON final_decisions(finalSignal)")
        db.execSQL(
            "CREATE INDEX IF NOT EXISTS index_final_decisions_eligibleForContract " +
                "ON final_decisions(eligibleForContract)"
        )
    }
}