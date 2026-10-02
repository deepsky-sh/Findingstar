package com.example.seoultsp.ui

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.addPathNodes
import androidx.compose.ui.unit.dp

/** 앱에서 쓰는 아이콘 (Material Symbols 경로 데이터). 별도 아이콘 라이브러리 없이 사용합니다. */
object AppIcons {
    val Play: ImageVector = icon("Play", "M8,5v14l11,-7z")
    val Pause: ImageVector = icon("Pause", "M6,19h4V5H6v14zM14,5v14h4V5h-4z")
    val SkipNext: ImageVector = icon("SkipNext", "M6,18l8.5,-6L6,6v12zM16,6v12h2V6h-2z")
    val Refresh: ImageVector = icon(
        "Refresh",
        "M17.65,6.35C16.2,4.9 14.21,4 12,4c-4.42,0 -7.99,3.58 -7.99,8s3.57,8 7.99,8c3.73,0 6.84,-2.55 " +
            "7.73,-6h-2.08c-0.82,2.33 -3.04,4 -5.65,4 -3.31,0 -6,-2.69 -6,-6s2.69,-6 6,-6c1.66,0 3.14,0.69 " +
            "4.22,1.78L13,11h7V4l-2.35,2.35z",
    )
    val Dice: ImageVector = icon(
        "Dice",
        "M19,3H5C3.9,3 3,3.9 3,5v14c0,1.1 0.9,2 2,2h14c1.1,0 2,-0.9 2,-2V5C21,3.9 20.1,3 19,3zM7.5,18" +
            "C6.67,18 6,17.33 6,16.5S6.67,15 7.5,15S9,15.67 9,16.5S8.33,18 7.5,18zM7.5,9C6.67,9 6,8.33 6,7.5" +
            "S6.67,6 7.5,6S9,6.67 9,7.5S8.33,9 7.5,9zM12,13.5c-0.83,0 -1.5,-0.67 -1.5,-1.5s0.67,-1.5 1.5,-1.5" +
            "s1.5,0.67 1.5,1.5S12.83,13.5 12,13.5zM16.5,18c-0.83,0 -1.5,-0.67 -1.5,-1.5s0.67,-1.5 1.5,-1.5" +
            "s1.5,0.67 1.5,1.5S17.33,18 16.5,18zM16.5,9c-0.83,0 -1.5,-0.67 -1.5,-1.5S15.67,6 16.5,6S18,6.67 " +
            "18,7.5S17.33,9 16.5,9z",
    )
    val Restore: ImageVector = icon(
        "Restore",
        "M13,3c-4.97,0 -9,4.03 -9,9L1,12l3.89,3.89 0.07,0.14L9,12L6,12c0,-3.87 3.13,-7 7,-7s7,3.13 7,7" +
            " -3.13,7 -7,7c-1.93,0 -3.68,-0.79 -4.94,-2.06l-1.42,1.42C8.27,19.99 10.51,21 13,21c4.97,0 9,-4.03 " +
            "9,-9s-4.03,-9 -9,-9zM12,8v5l4.28,2.54 0.72,-1.21 -3.5,-2.08L13.5,8L12,8z",
    )

    private fun icon(name: String, pathData: String): ImageVector =
        ImageVector.Builder(
            name = name,
            defaultWidth = 24.dp,
            defaultHeight = 24.dp,
            viewportWidth = 24f,
            viewportHeight = 24f,
        ).addPath(pathData = addPathNodes(pathData), fill = SolidColor(Color.Black)).build()
}
