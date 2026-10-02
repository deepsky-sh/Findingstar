package com.example.seoultsp.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import com.example.seoultsp.ga.SeoulAttractions

/** 알고리즘 흐름과 비용 정의를 설명하는 카드. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AlgorithmInfoCard(modifier: Modifier = Modifier) {
    val colors = MaterialTheme.colorScheme
    val steps = listOf("무작위 초기 개체군", "거리 평가", "엘리트 보존", "선택", "교차", "돌연변이", "다음 세대")
    SectionCard(title = "알고리즘 한눈에 보기", modifier = modifier) {
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            steps.forEachIndexed { index, step ->
                Row(
                    modifier = Modifier
                        .clip(CircleShape)
                        .background(colors.primaryContainer)
                        .padding(start = 3.dp, end = 10.dp, top = 3.dp, bottom = 3.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(
                        Modifier
                            .size(20.dp)
                            .clip(CircleShape)
                            .background(colors.primary),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text("${index + 1}", style = MaterialTheme.typography.labelSmall, color = colors.onPrimary)
                    }
                    Spacer(Modifier.width(6.dp))
                    Text(step, style = MaterialTheme.typography.labelMedium, color = colors.onPrimaryContainer)
                }
            }
        }
        Spacer(Modifier.height(14.dp))
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            InfoLine("개체(염색체)", "20곳의 방문 순서를 나타내는 순열")
            InfoLine("비용(COST)", "경복궁에서 출발해 모든 곳을 한 번씩 들르고 돌아오는 직선거리(하버사인) 합")
            InfoLine(
                "최적해",
                "Held-Karp 동적 계획법으로 미리 구한 정확한 답 " + "%.2f".format(SeoulAttractions.OPTIMAL_TOUR_KM) + " km",
            )
        }
    }
}

@Composable
private fun InfoLine(title: String, body: String) {
    Row {
        Text(
            title,
            modifier = Modifier.width(92.dp),
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.onSurface,
        )
        Text(body, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
