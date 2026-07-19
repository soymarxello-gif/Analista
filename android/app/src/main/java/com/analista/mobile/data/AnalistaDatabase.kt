package com.analista.mobile.data

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(entities = [ScanRunEntity::class, CandidateEntity::class], version = 1, exportSchema = false)
abstract class AnalistaDatabase : RoomDatabase() {
    abstract fun dao(): AnalistaDao
}
