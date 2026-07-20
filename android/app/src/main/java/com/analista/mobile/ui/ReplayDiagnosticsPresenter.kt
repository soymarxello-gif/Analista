package com.analista.mobile.ui

import com.analista.mobile.data.ReplayResultEntity

object ReplayDiagnosticsPresenter {
    data class Model(
        val status: String,
        val coverageLabel: String,
        val matchLabel: String,
        val mismatchLabel: String,
        val missingLabel: String,
        val reasons: List<String>,
        val trustworthy: Boolean,
        val hasData: Boolean
    )

    fun present(entity: ReplayResultEntity?): Model {
        if (entity == null) return Model(
            status = "NO_DATA",
            coverageLabel = "0/0",
            matchLabel = "0",
            mismatchLabel = "0",
            missingLabel = "0",
            reasons = listOf("replay_not_executed"),
            trustworthy = false,
            hasData = false
        )
        return Model(
            status = entity.status,
            coverageLabel = "${entity.replayedTickers}/${entity.expectedTickers}",
            matchLabel = entity.fullyMatchedTickers.toString(),
            mismatchLabel = entity.mismatchedTickers.toString(),
            missingLabel = entity.missingDatasetCount.toString(),
            reasons = entity.reasons.split('|').filter { it.isNotBlank() },
            trustworthy = entity.status == "COMPLETE" &&
                entity.expectedTickers > 0 &&
                entity.replayedTickers == entity.expectedTickers &&
                entity.fullyMatchedTickers == entity.expectedTickers &&
                entity.mismatchedTickers == 0 &&
                entity.missingDatasetCount == 0,
            hasData = true
        )
    }
}
