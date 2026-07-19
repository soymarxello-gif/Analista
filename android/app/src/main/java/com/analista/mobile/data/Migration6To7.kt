package com.analista.mobile.data

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

val MIGRATION_6_7 = object : Migration(6, 7) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE IF NOT EXISTS candidate_trade_plans (
                planId TEXT NOT NULL PRIMARY KEY,
                runId TEXT NOT NULL,
                ticker TEXT NOT NULL,
                priorResistance REAL NOT NULL,
                nextResistance REAL,
                swingLow REAL NOT NULL,
                closeLocationValue REAL NOT NULL,
                baseRangeAtr REAL NOT NULL,
                volatilityCompression REAL NOT NULL,
                resistanceTouches INTEGER NOT NULL,
                structureScore REAL NOT NULL,
                rs20VsSpy REAL,
                rs60VsSpy REAL,
                relativeStrengthScore REAL NOT NULL,
                relativeStrengthStatus TEXT NOT NULL,
                plannedEntry REAL NOT NULL,
                structuralStop REAL NOT NULL,
                structuralTarget REAL NOT NULL,
                stopType TEXT NOT NULL,
                stopAtrMultiple REAL NOT NULL,
                structuralRr REAL NOT NULL,
                riskPct REAL NOT NULL,
                rewardPct REAL NOT NULL,
                shares INTEGER NOT NULL,
                positionValue REAL NOT NULL,
                riskBudget REAL NOT NULL,
                riskPlanValid INTEGER NOT NULL,
                legacyRank INTEGER NOT NULL,
                tradeRank INTEGER NOT NULL,
                rankDelta INTEGER NOT NULL,
                auditedTradeScore REAL NOT NULL,
                reasons TEXT NOT NULL,
                engineVersion TEXT NOT NULL,
                calculatedAtUtc INTEGER NOT NULL
            )""".trimIndent()
        )
        db.execSQL("CREATE INDEX IF NOT EXISTS index_candidate_trade_plans_runId ON candidate_trade_plans(runId)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_candidate_trade_plans_ticker ON candidate_trade_plans(ticker)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_candidate_trade_plans_tradeRank ON candidate_trade_plans(tradeRank)")
    }
}
