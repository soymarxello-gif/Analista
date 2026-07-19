package com.analista.mobile.data

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "reproducibility_manifests",
    indices = [Index("runId"), Index("ticker"), Index("manifestHash")]
)
data class ReproducibilityManifestEntity(
    @PrimaryKey val manifestId: String,
    val runId: String,
    val ticker: String,
    val barsHash: String,
    val configurationHash: String,
    val universeHash: String,
    val manifestHash: String,
    val barCount: Int,
    val firstBarEpochSeconds: Long?,
    val lastBarEpochSeconds: Long?,
    val provider: String,
    val providerHost: String,
    val providerStatus: String,
    val fallbackUsed: Boolean,
    val cacheHit: Boolean,
    val retrievedAtUtc: Long,
    val engineVersion: String
)
