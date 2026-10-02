package com.example.seoultsp.ui.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.ui.graphics.Color

/**
 * Material3 1.2+ 컴포넌트가 쓰는 surfaceContainer 계열 색을 앱 팔레트에 맞춥니다.
 * (지정하지 않으면 기본 보라색 계열이 섞여 보입니다.)
 */
internal fun ColorScheme.withPlatformSurfaces(dark: Boolean): ColorScheme =
    if (dark) {
        copy(
            surfaceDim = Color(0xFF0B0F1A),
            surfaceBright = Color(0xFF263049),
            surfaceContainerLowest = Color(0xFF0B0F1A),
            surfaceContainerLow = Color(0xFF111827),
            surfaceContainer = Color(0xFF131A2A),
            surfaceContainerHigh = Color(0xFF1A2234),
            surfaceContainerHighest = Color(0xFF1E2639),
        )
    } else {
        copy(
            surfaceDim = Color(0xFFDDE1EC),
            surfaceBright = Color.White,
            surfaceContainerLowest = Color.White,
            surfaceContainerLow = Color(0xFFF8F9FC),
            surfaceContainer = Color(0xFFF4F5FA),
            surfaceContainerHigh = Color(0xFFF0F2F8),
            surfaceContainerHighest = Color(0xFFEEF0F7),
        )
    }
