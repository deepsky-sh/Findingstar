package com.example.seoultsp.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import com.example.seoultsp.ga.CrossoverMethod
import com.example.seoultsp.ga.GaConfig
import com.example.seoultsp.ga.MutationMethod
import com.example.seoultsp.ga.SelectionMethod
import com.example.seoultsp.sim.SimSpeed
import com.example.seoultsp.sim.SimulationController
import com.example.seoultsp.ui.theme.TabularNumbers
import kotlin.math.roundToInt

/** 유전자 알고리즘의 모든 인자를 조정하는 패널. */
@Composable
fun ParameterPanel(controller: SimulationController, modifier: Modifier = Modifier) {
    val config = controller.config
    val editable = controller.canEditParameters
    val update = controller::updateConfig

    Column(modifier, verticalArrangement = Arrangement.spacedBy(16.dp)) {
        SectionCard(
            title = "유전자 알고리즘 파라미터",
            subtitle = if (editable) {
                "값을 바꾸면 새 초기 개체군으로 다시 준비됩니다"
            } else {
                "실행 중에는 잠겨 있어요 · 초기화하면 다시 바꿀 수 있습니다"
            },
            trailing = {
                TextButton(onClick = controller::restoreDefaults, enabled = editable) {
                    Icon(AppIcons.Restore, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("기본값")
                }
            },
        ) {
            GroupHeader("개체군 · 세대")
            ParameterSlider(
                label = "개체 수 (Population)",
                value = config.populationSize.toFloat(),
                valueRange = GaConfig.POPULATION_RANGE.toFloatRange(),
                step = 10f,
                valueText = config.populationSize.toString(),
                onValueChange = { v -> update { it.copy(populationSize = v.roundToInt()) } },
                enabled = editable,
            )
            ParameterSlider(
                label = "최대 세대 수",
                value = config.generations.toFloat(),
                valueRange = GaConfig.GENERATION_RANGE.toFloatRange(),
                step = 50f,
                valueText = config.generations.toString(),
                onValueChange = { v -> update { it.copy(generations = v.roundToInt()) } },
                enabled = editable,
            )
            ParameterSlider(
                label = "엘리트 보존",
                value = config.eliteCount.toFloat(),
                valueRange = GaConfig.ELITE_RANGE.toFloatRange(),
                step = 1f,
                valueText = "${config.eliteCount}개",
                onValueChange = { v -> update { it.copy(eliteCount = v.roundToInt()) } },
                enabled = editable,
                caption = "가장 좋은 개체를 그대로 다음 세대에 남깁니다. 0이면 최고 기록이 사라질 수도 있어요.",
            )

            ThinDivider()
            GroupHeader("선택 (Selection)")
            SegmentedControl(
                options = SelectionMethod.entries,
                selected = config.selection,
                onSelect = { method -> update { it.copy(selection = method) } },
                label = { it.label },
                enabled = editable,
            )
            Description(config.selection.description)
            if (config.selection == SelectionMethod.Tournament) {
                ParameterSlider(
                    label = "토너먼트 크기 k",
                    value = config.tournamentSize.toFloat(),
                    valueRange = GaConfig.TOURNAMENT_RANGE.toFloatRange(),
                    step = 1f,
                    valueText = config.tournamentSize.toString(),
                    onValueChange = { v -> update { it.copy(tournamentSize = v.roundToInt()) } },
                    enabled = editable,
                )
            }

            ThinDivider()
            GroupHeader("교차 (Crossover)")
            SegmentedControl(
                options = CrossoverMethod.entries,
                selected = config.crossover,
                onSelect = { method -> update { it.copy(crossover = method) } },
                label = { it.label },
                enabled = editable,
            )
            Description(config.crossover.description)
            ParameterSlider(
                label = "교차율",
                value = config.crossoverRate.toFloat(),
                valueRange = 0f..1f,
                step = 0.05f,
                valueText = formatRate(config.crossoverRate),
                onValueChange = { v -> update { it.copy(crossoverRate = v.toDouble().roundTo(2)) } },
                enabled = editable,
                caption = "교차하지 않은 쌍은 부모를 그대로 복제합니다.",
            )

            ThinDivider()
            GroupHeader("돌연변이 (Mutation)")
            SegmentedControl(
                options = MutationMethod.entries,
                selected = config.mutation,
                onSelect = { method -> update { it.copy(mutation = method) } },
                label = { it.label },
                enabled = editable,
            )
            Description(config.mutation.description)
            ParameterSlider(
                label = "돌연변이율 (개체당)",
                value = config.mutationRate.toFloat(),
                valueRange = 0f..1f,
                step = 0.01f,
                valueText = formatRate(config.mutationRate),
                onValueChange = { v -> update { it.copy(mutationRate = v.toDouble().roundTo(2)) } },
                enabled = editable,
            )
        }

        RunSettingsCard(controller)
    }
}

@Composable
private fun RunSettingsCard(controller: SimulationController) {
    val colors = MaterialTheme.colorScheme
    val editable = controller.canEditParameters
    SectionCard(title = "실행 설정", subtitle = "속도는 실행 중에도 바꿀 수 있어요") {
        GroupHeader("애니메이션 속도")
        SegmentedControl(
            options = SimSpeed.entries,
            selected = controller.speed,
            onSelect = { controller.speed = it },
            label = { it.label },
        )

        ThinDivider()
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("난수 시드", style = MaterialTheme.typography.bodyMedium, color = colors.onSurface)
                Text(
                    "같은 시드와 파라미터면 항상 같은 결과가 나옵니다",
                    style = MaterialTheme.typography.bodySmall,
                    color = colors.onSurfaceVariant,
                )
            }
            Text(
                "#" + controller.config.seed,
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .background(colors.surfaceVariant)
                    .padding(horizontal = 10.dp, vertical = 6.dp),
                style = MaterialTheme.typography.labelLarge.merge(TabularNumbers),
                color = colors.onSurface,
            )
            Spacer(Modifier.width(8.dp))
            FilledTonalIconButton(onClick = controller::rerollSeed, enabled = editable) {
                Icon(AppIcons.Dice, contentDescription = "새 시드")
            }
        }
        Spacer(Modifier.height(12.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                "초기화할 때마다 새 시드 사용",
                modifier = Modifier.weight(1f),
                style = MaterialTheme.typography.bodyMedium,
                color = colors.onSurface,
            )
            Switch(
                checked = controller.newSeedEachRun,
                onCheckedChange = { controller.newSeedEachRun = it },
                colors = SwitchDefaults.colors(checkedTrackColor = colors.primary),
            )
        }
    }
}

@Composable
private fun Description(text: String) {
    Text(
        text = text,
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp, bottom = 4.dp),
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

private fun IntRange.toFloatRange(): ClosedFloatingPointRange<Float> = first.toFloat()..last.toFloat()

private fun Double.roundTo(decimals: Int): Double {
    var factor = 1.0
    repeat(decimals) { factor *= 10 }
    return (this * factor).roundToInt() / factor
}

private fun formatRate(rate: Double): String = "${(rate * 100).roundToInt()}%"
