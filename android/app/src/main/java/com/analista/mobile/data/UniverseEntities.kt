package com.analista.mobile.data

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "universe_snapshots",
    indices = [Index("effectiveDate"), Index("selectionRuleVersion"), Index("status")]
)
data class UniverseSnapshotEntity(
    @PrimaryKey val snapshotId: String,
    val effectiveDate: String,
    val selectionRuleVersion: String,
    val mode: String,
    val symbols: String,
    val symbolCount: Int,
    val eligibleCount: Int,
    val source: String,
    val status: String,
    val createdAtUtc: Long
)

@Entity(
    tableName = "universe_members",
    foreignKeys = [
        ForeignKey(
            entity = UniverseSnapshotEntity::class,
            parentColumns = ["snapshotId"],
            childColumns = ["snapshotId"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("snapshotId"), Index("ticker"), Index("eligible"), Index("instrumentType")]
)
data class UniverseMemberEntity(
    @PrimaryKey val memberId: String,
    val snapshotId: String,
    val ticker: String,
    val sector: String?,
    val industry: String?,
    val instrumentType: String,
    val adrStatus: String,
    val price: Double?,
    val marketCap: Long?,
    val averageDollarVolume20: Double?,
    val spreadPct: Double?,
    val eligible: Boolean,
    val exclusionReasons: String,
    val capturedAtUtc: Long
)
