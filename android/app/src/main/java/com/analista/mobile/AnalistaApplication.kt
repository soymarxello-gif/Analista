package com.analista.mobile

import android.app.Application
import androidx.room.Room
import com.analista.mobile.data.AlpacaCredentialsStore
import com.analista.mobile.data.AlpacaMarketDataClient
import com.analista.mobile.data.AnalistaDatabase
import com.analista.mobile.data.MIGRATION_1_2
import com.analista.mobile.data.MIGRATION_2_3
import com.analista.mobile.data.MIGRATION_3_4
import com.analista.mobile.data.MIGRATION_4_5
import com.analista.mobile.data.MIGRATION_5_6
import com.analista.mobile.data.MIGRATION_6_7
import com.analista.mobile.data.MIGRATION_7_8
import com.analista.mobile.data.MIGRATION_8_9
import com.analista.mobile.data.MarketDataGateway
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
                MIGRATION_8_9
            )
            .build()
    }
    private val yahoo by lazy { YahooFinanceClient(this) }
    val credentialsStore by lazy { AlpacaCredentialsStore(this) }
    val marketDataGateway by lazy {
        MarketDataGateway(yahoo, AlpacaMarketDataClient(), credentialsStore)
    }
    val repository by lazy { ScanRepository(database.dao(), yahoo, marketDataGateway) }
}
