// Тема (Material3, тёмная)
package ru.smartkam.patrol.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val Scheme = darkColorScheme(
    primary = Color(0xFF2563EB),
    onPrimary = Color.White,
    secondary = Color(0xFF64748B),
    surface = Color(0xFF10151D),
    background = Color(0xFF10151D),
    onSurface = Color(0xFFE2E8F0),
    onBackground = Color(0xFFE2E8F0),
    error = Color(0xFFDC2626),
)

@Composable
fun PatrolTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = Scheme, content = content)
}
