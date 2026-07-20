package com.analista.mobile.data

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

val MIGRATION_14_15 = object : Migration(14, 15) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("ALTER TABLE signal_contracts ADD COLUMN shares INTEGER NOT NULL DEFAULT 1")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN exitPrice REAL")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN exitTimestampUtc INTEGER")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN exitReason TEXT NOT NULL DEFAULT 'NONE'")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN entrySlippagePct REAL")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN exitSlippagePct REAL")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN commissionUsd REAL NOT NULL DEFAULT 0.0")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN grossPnlUsd REAL")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN netPnlUsd REAL")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN tradeReturnPct REAL")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN returnR REAL")
        db.execSQL("ALTER TABLE trade_outcomes ADD COLUMN costModelVersion TEXT NOT NULL DEFAULT 'NONE'")
    }
}
