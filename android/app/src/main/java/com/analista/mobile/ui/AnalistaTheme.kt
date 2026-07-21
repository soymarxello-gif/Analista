package com.analista.mobile.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val AnalistaDarkColors = darkColorScheme(
    primary = Color(0xFF67E8F9),
    onPrimary = Color(0xFF002B33),
    primaryContainer = Color(0xFF164E63),
    onPrimaryContainer = Color(0xFFCFFAFE),
    secondary = Color(0xFFA7F3D0),
    onSecondary = Color(0xFF052E25),
    tertiary = Color(0xFFFDE68A),
    onTertiary = Color(0xFF3F2E00),
    error = Color(0xFFFCA5A5),
    onError = Color(0xFF450A0A),
    background = Color(0xFF090D12),
    onBackground = Color(0xFFE5E7EB),
    surface = Color(0xFF111827),
    onSurface = Color(0xFFE5E7EB),
    surfaceVariant = Color(0xFF1F2937),
    onSurfaceVariant = Color(0xFFCBD5E1),
    outline = Color(0xFF475569)
)

@Composable
fun AnalistaTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = AnalistaDarkColors,
        typography = Typography(),
        content = content
    )
}
