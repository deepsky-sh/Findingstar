package com.example.seoultsp.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/** Material 색상표에 없는, 이 앱 고유의 색. */
@Immutable
data class ExtraColors(
    val heroStart: Color,
    val heroEnd: Color,
    val optimum: Color,
    val previousRun: Color,
    val river: Color,
    val mapBackground: Color,
    val mapGrid: Color,
)

private val LightColors = lightColorScheme(
    primary = Color(0xFF4F46E5),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFE0E7FF),
    onPrimaryContainer = Color(0xFF1E1B4B),
    secondary = Color(0xFF0284C7),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFE0F2FE),
    onSecondaryContainer = Color(0xFF0C4A6E),
    tertiary = Color(0xFFF59E0B),
    onTertiary = Color(0xFF3B2300),
    tertiaryContainer = Color(0xFFFEF3C7),
    onTertiaryContainer = Color(0xFF78350F),
    background = Color(0xFFF4F5FA),
    onBackground = Color(0xFF111827),
    surface = Color.White,
    onSurface = Color(0xFF111827),
    surfaceVariant = Color(0xFFEEF0F7),
    onSurfaceVariant = Color(0xFF5B6275),
    outline = Color(0xFFC3C8D6),
    outlineVariant = Color(0xFFE4E7EF),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFA5B4FC),
    onPrimary = Color(0xFF1E1B4B),
    primaryContainer = Color(0xFF3730A3),
    onPrimaryContainer = Color(0xFFE0E7FF),
    secondary = Color(0xFF7DD3FC),
    onSecondary = Color(0xFF082F49),
    secondaryContainer = Color(0xFF0C4A6E),
    onSecondaryContainer = Color(0xFFE0F2FE),
    tertiary = Color(0xFFFCD34D),
    onTertiary = Color(0xFF3B2300),
    tertiaryContainer = Color(0xFF78350F),
    onTertiaryContainer = Color(0xFFFEF3C7),
    background = Color(0xFF0B0F1A),
    onBackground = Color(0xFFE5E7EB),
    surface = Color(0xFF131A2A),
    onSurface = Color(0xFFE5E7EB),
    surfaceVariant = Color(0xFF1E2639),
    onSurfaceVariant = Color(0xFFA3ABBF),
    outline = Color(0xFF465069),
    outlineVariant = Color(0xFF263049),
)

private val LightExtra = ExtraColors(
    heroStart = Color(0xFF4338CA),
    heroEnd = Color(0xFF7C3AED),
    optimum = Color(0xFF059669),
    previousRun = Color(0xFF94A3B8),
    river = Color(0xFF7CC4F2),
    mapBackground = Color(0xFFF3F5FB),
    mapGrid = Color(0xFFE2E6F0),
)

private val DarkExtra = ExtraColors(
    heroStart = Color(0xFF312E81),
    heroEnd = Color(0xFF6D28D9),
    optimum = Color(0xFF34D399),
    previousRun = Color(0xFF64748B),
    river = Color(0xFF1E5A86),
    mapBackground = Color(0xFF0F1524),
    mapGrid = Color(0xFF1B2335),
)

val LocalExtraColors = staticCompositionLocalOf { LightExtra }

/** 숫자가 바뀌어도 폭이 흔들리지 않도록 고정폭 숫자를 씁니다. */
val TabularNumbers = TextStyle(fontFeatureSettings = "tnum")

private val AppTypography = Typography().let { base ->
    base.copy(
        displayMedium = base.displayMedium.copy(fontWeight = FontWeight.Bold, letterSpacing = (-1).sp),
        headlineSmall = base.headlineSmall.copy(fontWeight = FontWeight.Bold),
        titleLarge = base.titleLarge.copy(fontWeight = FontWeight.Bold),
        titleMedium = base.titleMedium.copy(fontWeight = FontWeight.SemiBold),
        labelLarge = base.labelLarge.copy(fontWeight = FontWeight.SemiBold),
    )
}

@Composable
fun SeoulTspTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colors: ColorScheme = (if (darkTheme) DarkColors else LightColors).withPlatformSurfaces(darkTheme)
    CompositionLocalProvider(LocalExtraColors provides if (darkTheme) DarkExtra else LightExtra) {
        MaterialTheme(colorScheme = colors, typography = AppTypography, content = content)
    }
}
