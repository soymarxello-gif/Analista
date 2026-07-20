package com.analista.mobile.data

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

val MIGRATION_13_14 = object : Migration(13, 14) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE IF NOT EXISTS universe_snapshots (
                snapshotId TEXT NOT NULL PRIMARY KEY,
                effectiveDate TEXT NOT NULL,
                selectionRuleVersion TEXT NOT NULL,
                mode TEXT NOT NULL,
                symbols TEXT NOT NULL,
                symbolCount INTEGER NOT NULL,
                eligibleCount INTEGER NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                createdAtUtc INTEGER NOT NULL
            )""".trimIndent()
        )
        db.execSQL("CREATE INDEX IF NOT EXISTS index_universe_snapshots_effectiveDate ON universe_snapshots(effectiveDate)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_universe_snapshots_selectionRuleVersion ON universe_snapshots(selectionRuleVersion)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_universe_snapshots_status ON universe_snapshots(status)")
        db.execSQL(
            """CREATE TABLE IF NOT EXISTS universe_members (
                memberId TEXT NOT NULL PRIMARY KEY,
                snapshotId TEXT NOT NULL,
                ticker TEXT NOT NULL,
                sector TEXT,
                industry TEXT,
                instrumentType TEXT NOT NULL,
                adrStatus TEXT NOT NULL,
                price REAL,
                marketCap INTEGER,
                averageDollarVolume20 REAL,
                spreadPct REAL,
                eligible INTEGER NOT NULL,
                exclusionReasons TEXT NOT NULL,
                capturedAtUtc INTEGER NOT NULL,
                FOREIGN KEY(snapshotId) REFERENCES universe_snapshots(snapshotId) ON DELETE CASCADE
            )""".trimIndent()
        )
        db.execSQL("CREATE INDEX IF NOT EXISTS index_universe_members_snapshotId ON universe_members(snapshotId)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_universe_members_ticker ON universe_members(ticker)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_universe_members_eligible ON universe_members(eligible)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_universe_members_instrumentType ON universe_members(instrumentType)")
    }
}
