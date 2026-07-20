package com.analista.mobile.data

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

val MIGRATION_11_12 = object : Migration(11, 12) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE IF NOT EXISTS fundamental_snapshots (
                snapshotId TEXT NOT NULL PRIMARY KEY,
                runId TEXT NOT NULL,
                ticker TEXT NOT NULL,
                revenueYoyPct REAL,
                revenueTrend TEXT NOT NULL,
                epsYoyPct REAL,
                epsTrend TEXT NOT NULL,
                grossMarginPct REAL,
                grossMarginDeltaPct REAL,
                operatingMarginPct REAL,
                operatingMarginDeltaPct REAL,
                netMarginPct REAL,
                netMarginDeltaPct REAL,
                debtToEquity REAL,
                debtToEbitda REAL,
                interestCoverage REAL,
                freeCashFlow REAL,
                priceToSales REAL,
                sectorPriceToSalesMedian REAL,
                earningsDateUtc INTEGER,
                earningsSessions INTEGER,
                earningsRiskStatus TEXT NOT NULL,
                dataAgeDays INTEGER,
                sector TEXT,
                coveragePct REAL NOT NULL,
                status TEXT NOT NULL,
                fundamentalScore REAL NOT NULL,
                reasons TEXT NOT NULL,
                engineVersion TEXT NOT NULL,
                capturedAtUtc INTEGER NOT NULL
            )""".trimIndent()
        )
        db.execSQL("CREATE INDEX IF NOT EXISTS index_fundamental_snapshots_runId ON fundamental_snapshots(runId)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_fundamental_snapshots_ticker ON fundamental_snapshots(ticker)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_fundamental_snapshots_status ON fundamental_snapshots(status)")
        db.execSQL(
            "CREATE INDEX IF NOT EXISTS index_fundamental_snapshots_earningsRiskStatus " +
                "ON fundamental_snapshots(earningsRiskStatus)"
        )
    }
}
