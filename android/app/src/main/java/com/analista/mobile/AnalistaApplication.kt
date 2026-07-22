package com.analista.mobile

import android.app.Application
import androidx.room.Room
import com.analista.mobile.data.AlpacaCredentialsStore
import com.analista.mobile.data.AlpacaMarketDataClient
import com.analista.mobile.data.AnalistaDatabase
import com.analista.mobile.data.DynamicTickerList
import com.analista.mobile.data.MIGRATION_1_2
import com.analista.mobile.data.MIGRATION_2_3
import com.analista.mobile.data.MIGRATION_3_4
import com.analista.mobile.data.MIGRATION_4_5
import com.analista.mobile.data.MIGRATION_5_6
import com.analista.mobile.data.MIGRATION_6_7
import com.analista.mobile.data.MIGRATION_7_8
import com.analista.mobile.data.MIGRATION_8_9
import com.analista.mobile.data.MIGRATION_9_10
import com.analista.mobile.data.MIGRATION_10_11
import com.analista.mobile.data.MIGRATION_11_12
import com.analista.mobile.data.MIGRATION_12_13
import com.analista.mobile.data.MIGRATION_13_14
import com.analista.mobile.data.MIGRATION_14_15
import com.analista.mobile.data.MIGRATION_15_16
import com.analista.mobile.data.MIGRATION_16_17
import com.analista.mobile.data.MarketDataGateway
import com.analista.mobile.data.InstitutionalEngineClient
import com.analista.mobile.data.InstitutionalEngineCredentialsStore
import com.analista.mobile.data.OfficialSourceCoordinator
import com.analista.mobile.data.OfficialSourceSettingsStore
import com.analista.mobile.data.RunDatasetCaptureService
import com.analista.mobile.data.RunDatasetStore
import com.analista.mobile.data.RunReplayService
import com.analista.mobile.data.ScanRepository
import com.analista.mobile.data.YahooFinanceClient

class AnalistaApplication : Application() {
    val database by lazy {
        Room.databaseBuilder(this, AnalistaDatabase::class.java, "analista.db")
            .addMigrations(
                MIGRATION_1_2,
                MIGRATION_2_3,
                MIGRATION_3_4,
                MIGRATION_4_5,
                MIGRATION_5_6,
                MIGRATION_6_7,
                MIGRATION_7_8,
                MIGRATION_8_9,
                MIGRATION_9_10,
                MIGRATION_10_11,
                MIGRATION_11_12,
                MIGRATION_12_13,
                MIGRATION_13_14,
                MIGRATION_14_15,
                MIGRATION_15_16,
                MIGRATION_16_17
            )
            .build()
    }
    private val yahoo by lazy { YahooFinanceClient(this) }
    private val datasetStore by lazy { RunDatasetStore(this) }
    private val datasetCapture by lazy { RunDatasetCaptureService(datasetStore) }
    val replayService by lazy { RunReplayService(database.replayDao(), datasetStore) }
    val credentialsStore by lazy { AlpacaCredentialsStore(this) }
    val institutionalEngineCredentials by lazy { InstitutionalEngineCredentialsStore(this) }
    val institutionalEngineClient by lazy { InstitutionalEngineClient(institutionalEngineCredentials) }
    val officialSourceSettings by lazy { OfficialSourceSettingsStore(this) }
    val officialSourceCoordinator by lazy { OfficialSourceCoordinator(officialSourceSettings) }
    val marketDataGateway by lazy {
        MarketDataGateway(yahoo, AlpacaMarketDataClient(), credentialsStore)
    }
    val repository by lazy {
        ScanRepository(
            database.dao(),
            yahoo,
            marketDataGateway,
            tickers = DynamicTickerList(ScanRepository.LEGACY_RESEARCH_TICKERS),
            datasetCapture = datasetCapture,
            officialSources = officialSourceCoordinator,
            institutionalEngine = institutionalEngineClient
        )
    }
}
