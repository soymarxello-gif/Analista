package com.analista.mobile.data

data class SourceStatus(
    val module: String,
    val provider: String,
    val status: String,
    val coverage: String,
    val capturedAtUtc: Long,
    val detail: String? = null
)
