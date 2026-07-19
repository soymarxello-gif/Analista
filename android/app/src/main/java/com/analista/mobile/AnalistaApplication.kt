package com.analista.mobile

import android.app.Application
import androidx.room.Room
import com.analista.mobile.data.AnalistaDatabase
import com.analista.mobile.data.MIGRATION_1_2
import com.analista.mobile.data.MIGRATION_2_3
import com.analista.mobile.data.MIGRATION_3_4
import com.analista.mobile.data.ScanRepository
import com.analista.mobile.data.YahooFinanceClient

class AnalistaApplication : Application() {
    val database by lazy {
        Room.databaseBuilder(this, AnalistaDatabase::class.java, "analista.db")
            .addMigrations(MIGRATION_1_2, MIGRATION_2_3, MIGRATION_3_4)
            .build()
    }
    val repository by lazy { ScanRepository(database.dao(), YahooFinanceClient(this)) }
}
