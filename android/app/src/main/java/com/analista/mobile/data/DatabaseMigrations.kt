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

val MIGRATION_3_4 = object : Migration(3, 4) {
    override fun migrate(db: SupportSQLiteDatabase) {
        val additions = listOf(
            "quoteStatus TEXT NOT NULL DEFAULT 'MISSING'",
            "executionQuoteQuality TEXT NOT NULL DEFAULT 'LOW'",
            "triggerConfirmed INTEGER NOT NULL DEFAULT 0",
            "setupType TEXT NOT NULL DEFAULT 'BREAKOUT_OR_PULLBACK'",
            "allVetoReasons TEXT NOT NULL DEFAULT ''",
            "penaltyReasons TEXT NOT NULL DEFAULT ''",
            "actionableEntry REAL",
            "actionableStop REAL",
            "actionableTarget REAL",
            "theoreticalEntry REAL",
            "theoreticalStop REAL",
            "theoreticalTarget REAL",
            "referenceClose REAL",
            "livePremarketPrice REAL",
            "bid REAL",
            "ask REAL",
            "spreadPct REAL",
            "openingGapPct REAL",
            "plannedTrigger REAL",
            "maximumEntry REAL",
            "actionabilityAtExecution TEXT NOT NULL DEFAULT 'QUOTE_UNCONFIRMED'",
            "quoteCapturedAtUtc INTEGER"
        )
        additions.forEach { definition ->
            db.execSQL("ALTER TABLE scan_candidates ADD COLUMN $definition")
        }
    }
}

val MIGRATION_4_5 = object : Migration(4, 5) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE IF NOT EXISTS candidate_analysis (
                analysisId TEXT NOT NULL PRIMARY KEY,
                runId TEXT NOT NULL,
                ticker TEXT NOT NULL,
                rsi6 REAL NOT NULL,
                rsi14Canonical REAL NOT NULL,
                rsi6GtRsi14 INTEGER NOT NULL,
                ema20 REAL NOT NULL,
                ema50 REAL NOT NULL,
                ema200 REAL NOT NULL,
                priceVsEma20Pct REAL NOT NULL,
                priceVsEma50Pct REAL NOT NULL,
                priceVsEma200Pct REAL NOT NULL,
                weeklyTrend TEXT NOT NULL,
                assetQualityScore REAL NOT NULL,
                setupQualityScore REAL NOT NULL,
                contextScore REAL NOT NULL,
                institutionalScore REAL NOT NULL,
                riskScore REAL NOT NULL,
                finalTradeScore REAL NOT NULL,
                stopAtrMultiple REAL NOT NULL,
                stopAtrStatus TEXT NOT NULL,
                scoreBreakdown TEXT NOT NULL,
                engineVersion TEXT NOT NULL,
                calculatedAtUtc INTEGER NOT NULL
            )""".trimIndent()
        )
        db.execSQL("CREATE INDEX IF NOT EXISTS index_candidate_analysis_runId ON candidate_analysis(runId)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_candidate_analysis_ticker ON candidate_analysis(ticker)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_candidate_analysis_finalTradeScore ON candidate_analysis(finalTradeScore)")
    }
}

val MIGRATION_5_6 = object : Migration(5, 6) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE IF NOT EXISTS signal_contracts (
                signalId TEXT NOT NULL PRIMARY KEY,
                runId TEXT NOT NULL,
                ticker TEXT NOT NULL,
                signal TEXT NOT NULL,
                decisionTimestampUtc INTEGER NOT NULL,
                referencePrice REAL NOT NULL,
                triggerPrice REAL NOT NULL,
                maximumEntry REAL NOT NULL,
                stopPrice REAL NOT NULL,
                targetPrice REAL NOT NULL,
                expirationSessions INTEGER NOT NULL,
                engineVersion TEXT NOT NULL,
                createdAtUtc INTEGER NOT NULL
            )""".trimIndent()
        )
        db.execSQL("CREATE INDEX IF NOT EXISTS index_signal_contracts_runId ON signal_contracts(runId)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_signal_contracts_ticker ON signal_contracts(ticker)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_signal_contracts_decisionTimestampUtc ON signal_contracts(decisionTimestampUtc)")
        db.execSQL(
            """CREATE TABLE IF NOT EXISTS trade_outcomes (
                signalId TEXT NOT NULL PRIMARY KEY,
                ticker TEXT NOT NULL,
                evaluatedAtUtc INTEGER NOT NULL,
                triggered INTEGER NOT NULL,
                triggerTimestampUtc INTEGER,
                entryFill REAL,
                stopHit INTEGER NOT NULL,
                targetHit INTEGER NOT NULL,
                firstExitEvent TEXT NOT NULL,
                return1dPct REAL,
                return3dPct REAL,
                return5dPct REAL,
                return10dPct REAL,
                return20dPct REAL,
                mfePct REAL,
                maePct REAL,
                holdingSessions INTEGER NOT NULL,
                ambiguousSameBar INTEGER NOT NULL,
                status TEXT NOT NULL
            )""".trimIndent()
        )
        db.execSQL("CREATE INDEX IF NOT EXISTS index_trade_outcomes_ticker ON trade_outcomes(ticker)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_trade_outcomes_evaluatedAtUtc ON trade_outcomes(evaluatedAtUtc)")
    }
}
