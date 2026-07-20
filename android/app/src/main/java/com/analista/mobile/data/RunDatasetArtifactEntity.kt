package com.analista.mobile.data

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "run_dataset_artifacts",
    indices = [Index("runId"), Index("datasetType"), Index("contentHash")]
)
data class RunDatasetArtifactEntity(
    @PrimaryKey val artifactId: String,
    val runId: String,
    val ticker: String?,
    val datasetType: String,
    val contentHash: String,
    val relativePath: String,
    val uncompressedBytes: Long,
    val compressedBytes: Long,
    val codecVersion: String,
    val createdAtUtc: Long
)
