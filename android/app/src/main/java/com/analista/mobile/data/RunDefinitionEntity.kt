package com.analista.mobile.data

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "run_definitions",
    indices = [Index("runId"), Index("universeVersion"), Index("configurationVersion")]
)
data class RunDefinitionEntity(
    @PrimaryKey val definitionId: String,
    val runId: String,
    val universeName: String,
    val universeVersion: String,
    val universeSymbolsCsv: String,
    val universeHash: String,
    val configurationVersion: String,
    val configurationJson: String,
    val configurationHash: String,
    val engineBundleVersion: String,
    val createdAtUtc: Long
)
