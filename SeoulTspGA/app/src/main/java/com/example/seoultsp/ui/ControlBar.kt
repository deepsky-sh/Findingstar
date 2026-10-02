package com.example.seoultsp.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import com.example.seoultsp.sim.SimStatus
import com.example.seoultsp.sim.SimulationController

/** 화면 아래에 고정된 실행 컨트롤: 초기화 · 시작/일시정지 · 한 세대 진행. */
@Composable
fun ControlBar(controller: SimulationController, modifier: Modifier = Modifier) {
    val colors = MaterialTheme.colorScheme
    val status = controller.status
    val history = controller.history
    val progress = (history.lastOrNull()?.generation ?: 0).toFloat() / controller.config.generations

    val (icon, text) = when (status) {
        SimStatus.Ready -> AppIcons.Play to "시작"
        SimStatus.Running -> AppIcons.Pause to "일시정지"
        SimStatus.Paused -> AppIcons.Play to "계속"
        SimStatus.Finished -> AppIcons.Refresh to "다시 실행"
    }

    Surface(modifier = modifier.fillMaxWidth(), color = colors.surface, shadowElevation = 16.dp) {
        Column(Modifier.windowInsetsPadding(WindowInsets.navigationBars)) {
            Box(
                Modifier
                    .fillMaxWidth()
                    .height(3.dp)
                    .background(colors.surfaceVariant),
            ) {
                Box(
                    Modifier
                        .fillMaxWidth(progress.coerceIn(0f, 1f))
                        .fillMaxHeight()
                        .background(colors.primary),
                )
            }
            Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                Row(
                    modifier = Modifier
                        .widthIn(max = 640.dp)
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    LabeledIconButton(
                        icon = AppIcons.Refresh,
                        label = "초기화",
                        enabled = status != SimStatus.Ready || history.size > 1,
                        onClick = controller::reset,
                    )
                    Button(
                        onClick = controller::playPause,
                        modifier = Modifier
                            .weight(1f)
                            .height(56.dp),
                        shape = RoundedCornerShape(18.dp),
                    ) {
                        Icon(icon, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text(text, style = MaterialTheme.typography.titleMedium)
                    }
                    LabeledIconButton(
                        icon = AppIcons.SkipNext,
                        label = "1세대",
                        enabled = status == SimStatus.Ready || status == SimStatus.Paused,
                        onClick = controller::stepOnce,
                    )
                }
            }
        }
    }
}

@Composable
private fun LabeledIconButton(icon: ImageVector, label: String, enabled: Boolean, onClick: () -> Unit) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        FilledTonalIconButton(onClick = onClick, enabled = enabled, modifier = Modifier.size(44.dp)) {
            Icon(icon, contentDescription = label)
        }
        Text(
            label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = if (enabled) 1f else 0.5f),
        )
    }
}
