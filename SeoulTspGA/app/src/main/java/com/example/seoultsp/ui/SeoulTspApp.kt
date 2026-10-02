package com.example.seoultsp.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.seoultsp.sim.SimulationController

/** 앱 전체 화면. 폭이 넓으면(태블릿·가로 화면) 시각화와 파라미터를 좌우로 나눠 보여 줍니다. */
@Composable
fun SeoulTspApp(controller: SimulationController, modifier: Modifier = Modifier) {
    var selected by remember { mutableStateOf<Int?>(null) }

    Scaffold(
        modifier = modifier,
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar = { ControlBar(controller) },
    ) { padding ->
        BoxWithConstraints(
            Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            val visuals: @Composable () -> Unit = {
                HeroHeader(controller)
                RouteMapCard(
                    attractions = controller.attractions,
                    tour = controller.bestTour,
                    cost = controller.bestCost,
                    selected = selected,
                    onSelect = { selected = it },
                )
                ConvergenceChartCard(
                    history = controller.history,
                    totalGenerations = controller.config.generations,
                    previousRun = controller.previousRun,
                )
            }
            if (maxWidth >= 840.dp) {
                Row(
                    Modifier
                        .fillMaxSize()
                        .padding(horizontal = 24.dp),
                    horizontalArrangement = Arrangement.spacedBy(24.dp),
                ) {
                    Column(
                        Modifier
                            .weight(1.4f)
                            .fillMaxHeight()
                            .verticalScroll(rememberScrollState())
                            .padding(vertical = 24.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                    ) { visuals() }
                    Column(
                        Modifier
                            .weight(1f)
                            .fillMaxHeight()
                            .verticalScroll(rememberScrollState())
                            .padding(vertical = 24.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                    ) {
                        ParameterPanel(controller)
                        AlgorithmInfoCard()
                    }
                }
            } else {
                Column(
                    Modifier
                        .fillMaxSize()
                        .verticalScroll(rememberScrollState())
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    visuals()
                    ParameterPanel(controller)
                    AlgorithmInfoCard()
                }
            }
        }
    }
}
