package com.analista.mobile.data

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

val MIGRATION_14_15 = object : Migration(14, 15) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("ALTER TABLE signal_contracts ADD COLUMN shares INTEGER NOT NULL DEFAULT 0")
        db.execSQL("ALTER TABLE signal_contracts ADD COLUMN positionValue REAL NOT NULL DEFAULT 0")
        db.execSQL("ALTER TABLE signal_contracts ADD COLUMN riskBudget REAL NOT NULL DEFAULT 0")

        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN exitTimestampUtc INTEGER")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN exitFill REAL")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN exitReason TEXT NOT NULL DEFAULT 'NONE'")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN tradeReturnPct REAL")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN tradeReturnR REAL")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN grossPnl REAL")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN netPnl REAL")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN totalCosts REAL")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN costModelVersion TEXT NOT NULL DEFAULT 'legacy-zero-cost'")
    }
}
