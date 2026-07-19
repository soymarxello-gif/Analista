package com.analista.mobile.data

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

val MIGRATION_1_2 = object : Migration(1, 2) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("ALTER TABLE scan_runs ADD COLUMN durationMs INTEGER NOT NULL DEFAULT 0")
        db.execSQL("ALTER TABLE scan_runs ADD COLUMN cacheHitCount INTEGER NOT NULL DEFAULT 0")
        db.execSQL("ALTER TABLE scan_runs ADD COLUMN retryCount INTEGER NOT NULL DEFAULT 0")
        db.execSQL(
            """CREATE TABLE IF NOT EXISTS backtest_outcomes (
                outcomeId TEXT NOT NULL PRIMARY KEY,
                sourceRunId TEXT NOT NULL,
                ticker TEXT NOT NULL,
                signal TEXT NOT NULL,
                sourceClose REAL NOT NULL,
                latestClose REAL NOT NULL,
                returnPct REAL NOT NULL,
                evaluatedAtUtc INTEGER NOT NULL
            )""".trimIndent()
        )
        db.execSQL("CREATE INDEX IF NOT EXISTS index_backtest_outcomes_ticker ON backtest_outcomes(ticker)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_backtest_outcomes_sourceRunId ON backtest_outcomes(sourceRunId)")
        db.execSQL(
            """CREATE TABLE IF NOT EXISTS market_snapshots (
                snapshotId TEXT NOT NULL PRIMARY KEY,
                runId TEXT NOT NULL,
                symbol TEXT NOT NULL,
                label TEXT NOT NULL,
                close REAL NOT NULL,
                changePct REAL NOT NULL,
                capturedAtUtc INTEGER NOT NULL
            )""".trimIndent()
        )
    }
}

val MIGRATION_2_3 = object : Migration(2, 3) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE IF NOT EXISTS candidate_enrichment (
                enrichmentId TEXT NOT NULL PRIMARY KEY,
                runId TEXT NOT NULL,
                ticker TEXT NOT NULL,
                marketCap INTEGER,
                trailingPe REAL,
                priceToSales REAL,
                epsTrailing REAL,
                revenueGrowthPct REAL,
                grossMarginPct REAL,
                operatingMarginPct REAL,
                profitMarginPct REAL,
                debtToEquity REAL,
                optionsPutCallOi REAL,
                optionsNearCallOi INTEGER,
                optionsNearPutOi INTEGER,
                optionsExpiry INTEGER,
                fundamentalsStatus TEXT NOT NULL,
                optionsStatus TEXT NOT NULL,
                capturedAtUtc INTEGER NOT NULL
            )""".trimIndent()
        )
        db.execSQL("CREATE INDEX IF NOT EXISTS index_candidate_enrichment_runId ON candidate_enrichment(runId)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_candidate_enrichment_ticker ON candidate_enrichment(ticker)")
    }
}
