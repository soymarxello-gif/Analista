package com.analista.mobile

import android.app.Application
import androidx.room.Room
import com.analista.mobile.data.AnalistaDatabase
import com.analista.mobile.data.ScanRepository
import com.analista.mobile.data.YahooFinanceClient

class AnalistaApplication : Application() {
    val database by lazy {
        Room.databaseBuilder(this, AnalistaDatabase::class.java, "analista.db")
            .fallbackToDestructiveMigration()
            .build()
    }
    val repository by lazy { ScanRepository(database.dao(), YahooFinanceClient(this)) }
}
