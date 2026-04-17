package com.communionafterdark.cad.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val CadColorScheme = darkColorScheme(
    primary = AccentRed,
    onPrimary = White,
    primaryContainer = SelectedBg,
    onPrimaryContainer = White,
    secondary = TextSecondary,
    onSecondary = Black,
    background = Black,
    onBackground = White,
    surface = Surface,
    onSurface = TextSecondary,
    surfaceVariant = SurfaceVariant,
    onSurfaceVariant = TextSecondary,
    outline = Border,
    error = AccentRed,
)

@Composable
fun CadTheme(
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = CadColorScheme,
        typography = CadTypography,
        content = content,
    )
}
