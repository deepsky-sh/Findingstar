package com.example.seoultsp.ui

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.seoultsp.ga.SeoulAttractions
import com.example.seoultsp.sim.SimStatus
import com.example.seoultsp.sim.SimulationController
import com.example.seoultsp.ui.theme.LocalExtraColors
import com.example.seoultsp.ui.theme.TabularNumbers

/** 화면 맨 위의 요약 영역: 현재 최단 거리, 진행률, 개선율, 최적해와의 차이. */
@Composable
fun HeroHeader(controller: SimulationController, modifier: Modifier = Modifier) {
    val extra = LocalExtraColors.current
    val history = controller.history
    val generation = history.lastOrNull()?.generation ?: 0
    val total = controller.config.generations
    val initialBest = history.firstOrNull()?.best ?: controller.bestCost
    val best = controller.bestCost
    val improvement = if (initialBest > 0) (initialBest - best) / initialBest else 0.0
    val gap = best / SeoulAttractions.OPTIMAL_TOUR_KM - 1
    val reachedOptimum = gap < 1e-9

    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(28.dp))
            .background(Brush.linearGradient(listOf(extra.heroStart, extra.heroEnd)))
            .padding(20.dp),
    ) {
        Column {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "서울 관광지 20곳 순회 외판원 문제",
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.labelMedium,
                    color = Color.White.copy(alpha = 0.75f),
                )
                StatusPill(controller.status)
            }
            Text(
                "유전자 알고리즘 시뮬레이터",
                style = MaterialTheme.typography.titleLarge,
                color = Color.White,
            )

            Spacer(Modifier.height(18.dp))
            Text(
                "현재까지 찾은 최단 경로",
                style = MaterialTheme.typography.labelMedium,
                color = Color.White.copy(alpha = 0.75f),
            )
            Row(verticalAlignment = Alignment.Bottom) {
                Text(
                    text = formatKm(best),
                    style = MaterialTheme.typography.displayMedium.merge(TabularNumbers),
                    color = Color.White,
                )
                Text(
                    text = " km",
                    modifier = Modifier.padding(bottom = 8.dp),
                    style = MaterialTheme.typography.titleLarge,
                    color = Color.White.copy(alpha = 0.8f),
                )
            }

            Spacer(Modifier.height(12.dp))
            ProgressTrack(
                fraction = if (total > 0) generation.toFloat() / total else 0f,
                modifier = Modifier.fillMaxWidth(),
            )

            Spacer(Modifier.height(14.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                HeroStat("세대", "$generation / $total", Modifier.weight(1f))
                HeroStat("초기 대비 개선", formatPercent(improvement), Modifier.weight(1f))
                HeroStat(
                    label = "최적해 대비",
                    value = if (reachedOptimum) "최적 도달" else "+" + formatPercent(gap),
                    modifier = Modifier.weight(1f),
                    highlight = reachedOptimum,
                )
            }
        }
    }
}

@Composable
private fun HeroStat(label: String, value: String, modifier: Modifier = Modifier, highlight: Boolean = false) {
    Column(
        modifier
            .clip(RoundedCornerShape(16.dp))
            .background(Color.White.copy(alpha = if (highlight) 0.24f else 0.12f))
            .padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = Color.White.copy(alpha = 0.75f), maxLines = 1)
        Spacer(Modifier.height(2.dp))
        Text(
            value,
            style = MaterialTheme.typography.titleSmall.merge(TabularNumbers).copy(fontWeight = FontWeight.Bold),
            color = Color.White,
            maxLines = 1,
        )
    }
}

@Composable
private fun ProgressTrack(fraction: Float, modifier: Modifier = Modifier) {
    Box(
        modifier
            .height(6.dp)
            .clip(CircleShape)
            .background(Color.White.copy(alpha = 0.2f)),
    ) {
        Box(
            Modifier
                .fillMaxWidth(fraction.coerceIn(0f, 1f))
                .fillMaxHeight()
                .clip(CircleShape)
                .background(Color.White),
        )
    }
}

@Composable
private fun StatusPill(status: SimStatus) {
    val dotColor = when (status) {
        SimStatus.Ready -> Color(0xFFE0E7FF)
        SimStatus.Running -> Color(0xFF6EE7B7)
        SimStatus.Paused -> Color(0xFFFCD34D)
        SimStatus.Finished -> Color(0xFF93C5FD)
    }
    val pulse by rememberInfiniteTransition(label = "pulse").animateFloat(
        initialValue = 1f,
        targetValue = 0.3f,
        animationSpec = infiniteRepeatable(tween(700), RepeatMode.Reverse),
        label = "pulseAlpha",
    )
    Row(
        modifier = Modifier
            .clip(CircleShape)
            .background(Color.White.copy(alpha = 0.16f))
            .padding(horizontal = 12.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .size(8.dp)
                .alpha(if (status == SimStatus.Running) pulse else 1f)
                .clip(CircleShape)
                .background(dotColor),
        )
        Spacer(Modifier.width(6.dp))
        Text(status.label, style = MaterialTheme.typography.labelMedium, color = Color.White)
    }
}
