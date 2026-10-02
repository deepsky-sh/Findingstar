package com.example.seoultsp.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import com.example.seoultsp.ga.SeoulAttractions
import com.example.seoultsp.sim.GenerationPoint
import com.example.seoultsp.sim.RunRecord
import com.example.seoultsp.ui.theme.LocalExtraColors
import com.example.seoultsp.ui.theme.TabularNumbers
import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.roundToInt

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ConvergenceChartCard(
    history: List<GenerationPoint>,
    totalGenerations: Int,
    previousRun: RunRecord?,
    modifier: Modifier = Modifier,
) {
    val colors = MaterialTheme.colorScheme
    val extra = LocalExtraColors.current
    SectionCard(
        title = "수렴 그래프",
        subtitle = "세대가 진행될수록 경로 비용(km)이 줄어드는 과정 · 그래프를 눌러 값 확인",
        modifier = modifier,
    ) {
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(14.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            LegendItem(colors.primary, "세대 최우수")
            LegendItem(colors.tertiary, "세대 평균")
            LegendItem(extra.optimum, "최적해 " + "%.2f".format(SeoulAttractions.OPTIMAL_TOUR_KM) + " km", dashed = true)
            if (previousRun != null) {
                LegendItem(extra.previousRun, "이전 실행 " + formatKm(previousRun.finalCost) + " km", dashed = true)
            }
        }
        Spacer(Modifier.height(12.dp))
        ConvergenceChart(
            history = history,
            totalGenerations = totalGenerations,
            optimum = SeoulAttractions.OPTIMAL_TOUR_KM,
            previous = previousRun?.bestCurve,
            modifier = Modifier.fillMaxWidth().height(240.dp),
        )
    }
}

@Composable
private fun LegendItem(color: Color, text: String, dashed: Boolean = false) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Canvas(Modifier.size(width = 18.dp, height = 10.dp)) {
            drawLine(
                color = color,
                start = Offset(0f, size.height / 2),
                end = Offset(size.width, size.height / 2),
                strokeWidth = 3.dp.toPx(),
                cap = StrokeCap.Round,
                pathEffect = if (dashed) PathEffect.dashPathEffect(floatArrayOf(4.dp.toPx(), 4.dp.toPx())) else null,
            )
        }
        Spacer(Modifier.width(6.dp))
        Text(text, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/** 세대(가로축)에 따른 비용(세로축) 꺾은선 그래프. */
@Composable
fun ConvergenceChart(
    history: List<GenerationPoint>,
    totalGenerations: Int,
    optimum: Double,
    previous: List<Double>?,
    modifier: Modifier = Modifier,
) {
    val colors = MaterialTheme.colorScheme
    val extra = LocalExtraColors.current
    val textMeasurer = rememberTextMeasurer()
    val axisStyle = MaterialTheme.typography.labelSmall.merge(TabularNumbers).copy(color = colors.onSurfaceVariant)
    val tooltipStyle = MaterialTheme.typography.labelMedium.merge(TabularNumbers).copy(color = colors.inverseOnSurface)
    val optimumStyle = axisStyle.copy(color = extra.optimum)
    var scrubX by remember { mutableStateOf<Float?>(null) }

    Canvas(
        modifier = modifier
            .pointerInput(Unit) {
                detectTapGestures(onTap = { tap -> scrubX = if (scrubX == null) tap.x else null })
            }
            .pointerInput(Unit) {
                detectHorizontalDragGestures(
                    onDragStart = { scrubX = it.x },
                    onDragEnd = { scrubX = null },
                    onDragCancel = { scrubX = null },
                ) { change, _ ->
                    scrubX = change.position.x
                    change.consume()
                }
            },
    ) {
        if (history.isEmpty()) return@Canvas
        val left = 40.dp.toPx()
        val right = 12.dp.toPx()
        val top = 12.dp.toPx()
        val bottom = 24.dp.toPx()
        val plotW = size.width - left - right
        val plotH = size.height - top - bottom
        if (plotW <= 0f || plotH <= 0f) return@Canvas

        // 축 범위
        var lo = optimum
        var hi = optimum
        for (p in history) {
            lo = min(lo, p.best)
            hi = max(hi, p.average)
        }
        previous?.forEach {
            lo = min(lo, it)
            hi = max(hi, it)
        }
        val yTicks = niceTicks(lo, hi, 5)
        val yMin = yTicks.first()
        val yMax = yTicks.last()
        val xMax = maxOf(totalGenerations, history.last().generation, (previous?.size ?: 1) - 1).coerceAtLeast(1)

        fun x(generation: Int): Float = left + plotW * generation / xMax
        fun y(value: Double): Float = top + (plotH * (1 - (value - yMin) / (yMax - yMin))).toFloat()

        // 눈금과 보조선
        val grid = colors.outlineVariant
        for (v in yTicks) {
            val yy = y(v)
            drawLine(grid, Offset(left, yy), Offset(left + plotW, yy), strokeWidth = 1.dp.toPx())
            val label = textMeasurer.measure(AnnotatedString(formatTick(v)), style = axisStyle)
            drawText(label, topLeft = Offset(left - 6.dp.toPx() - label.size.width, yy - label.size.height / 2f))
        }
        for (t in niceTicks(0.0, xMax.toDouble(), 5)) {
            if (t > xMax + 1e-9) continue
            val xx = x(t.roundToInt())
            val label = textMeasurer.measure(AnnotatedString(formatTick(t)), style = axisStyle)
            val lx = (xx - label.size.width / 2f).coerceIn(left - label.size.width / 2f, size.width - label.size.width.toFloat())
            drawText(label, topLeft = Offset(lx, top + plotH + 6.dp.toPx()))
        }

        val stride = max(1, ceil(history.size / plotW.toDouble()).toInt())
        fun series(count: Int, value: (Int) -> Double): Path = Path().apply {
            var first = true
            var i = 0
            while (i < count) {
                val px = x(i)
                val py = y(value(i))
                if (first) moveTo(px, py) else lineTo(px, py)
                first = false
                i = if (i == count - 1) count else min(i + stride, count - 1)
            }
        }

        // 최적해 기준선
        val optimumY = y(optimum)
        drawLine(
            color = extra.optimum,
            start = Offset(left, optimumY),
            end = Offset(left + plotW, optimumY),
            strokeWidth = 1.5.dp.toPx(),
            pathEffect = PathEffect.dashPathEffect(floatArrayOf(6.dp.toPx(), 5.dp.toPx())),
        )
        val optimumLabel = textMeasurer.measure(AnnotatedString("최적 " + formatKm(optimum)), style = optimumStyle)
        drawText(
            optimumLabel,
            topLeft = Offset(left + plotW - optimumLabel.size.width, optimumY - optimumLabel.size.height - 2.dp.toPx()),
        )

        // 이전 실행
        if (previous != null && previous.size > 1) {
            drawPath(
                path = series(previous.size) { previous[it] },
                color = extra.previousRun,
                style = Stroke(
                    width = 1.8.dp.toPx(),
                    join = StrokeJoin.Round,
                    pathEffect = PathEffect.dashPathEffect(floatArrayOf(5.dp.toPx(), 4.dp.toPx())),
                ),
            )
        }

        // 평균
        drawPath(
            path = series(history.size) { history[it].average },
            color = colors.tertiary,
            style = Stroke(width = 1.6.dp.toPx(), join = StrokeJoin.Round),
        )

        // 최우수 + 아래 영역
        val bestPath = series(history.size) { history[it].best }
        val area = Path().apply {
            addPath(bestPath)
            lineTo(x(history.size - 1), top + plotH)
            lineTo(x(0), top + plotH)
            close()
        }
        drawPath(
            path = area,
            brush = Brush.verticalGradient(
                colors = listOf(colors.primary.copy(alpha = 0.22f), colors.primary.copy(alpha = 0f)),
                startY = top,
                endY = top + plotH,
            ),
        )
        drawPath(bestPath, colors.primary, style = Stroke(width = 2.6.dp.toPx(), join = StrokeJoin.Round, cap = StrokeCap.Round))

        // 최적해에 처음 도달한 세대
        val hit = history.indexOfFirst { it.bestSoFar <= optimum + 1e-6 }
        if (hit >= 0) {
            val c = Offset(x(hit), y(history[hit].bestSoFar))
            drawCircle(colors.surface, radius = 6.dp.toPx(), center = c)
            drawCircle(extra.optimum, radius = 4.5.dp.toPx(), center = c)
        }

        // 현재 세대
        val last = history.last()
        val lastPoint = Offset(x(history.size - 1), y(last.best))
        drawCircle(colors.surface, radius = 6.dp.toPx(), center = lastPoint)
        drawCircle(colors.primary, radius = 4.dp.toPx(), center = lastPoint)

        // 터치한 위치의 값
        val sx = scrubX
        if (sx != null) {
            val generation = (((sx - left) / plotW) * xMax).roundToInt().coerceIn(0, history.size - 1)
            val point = history[generation]
            val gx = x(generation)
            drawLine(colors.onSurfaceVariant.copy(alpha = 0.6f), Offset(gx, top), Offset(gx, top + plotH), strokeWidth = 1.dp.toPx())
            drawCircle(colors.tertiary, radius = 4.dp.toPx(), center = Offset(gx, y(point.average)))
            drawCircle(colors.primary, radius = 4.5.dp.toPx(), center = Offset(gx, y(point.best)))
            val lines = buildList {
                add("${point.generation}세대")
                add("최우수 ${"%.2f".format(point.best)} km")
                add("평균 ${"%.2f".format(point.average)} km")
                previous?.getOrNull(generation)?.let { add("이전 ${"%.2f".format(it)} km") }
            }
            val tip = textMeasurer.measure(AnnotatedString(lines.joinToString("\n")), style = tooltipStyle)
            val pad = 8.dp.toPx()
            val boxSize = Size(tip.size.width + pad * 2, tip.size.height + pad * 2)
            val boxX = if (gx + 10.dp.toPx() + boxSize.width <= size.width) gx + 10.dp.toPx() else gx - 10.dp.toPx() - boxSize.width
            val boxTopLeft = Offset(boxX.coerceAtLeast(0f), top)
            drawRoundRect(colors.inverseSurface.copy(alpha = 0.92f), topLeft = boxTopLeft, size = boxSize, cornerRadius = CornerRadius(8.dp.toPx()))
            drawText(tip, topLeft = boxTopLeft + Offset(pad, pad))
        }
    }
}

/** 보기 좋은 간격(1, 2, 5 × 10ⁿ)의 눈금 값들. 첫 값 ≤ lo, 마지막 값 ≥ hi. */
internal fun niceTicks(lo: Double, hi: Double, targetCount: Int): List<Double> {
    val span = if (hi - lo < 1e-9) 1.0 else hi - lo
    val step = niceNumber(span / (targetCount - 1).coerceAtLeast(1))
    val start = floor(lo / step) * step
    val end = ceil(hi / step) * step
    val ticks = ArrayList<Double>()
    var v = start
    while (v <= end + step * 1e-6) {
        ticks += if (abs(v) < step * 1e-9) 0.0 else v
        v += step
    }
    if (ticks.size < 2) ticks += start + step
    return ticks
}

private fun niceNumber(raw: Double): Double {
    val exponent = floor(log10(raw))
    val fraction = raw / 10.0.pow(exponent)
    val nice = when {
        fraction < 1.5 -> 1.0
        fraction < 3.0 -> 2.0
        fraction < 7.0 -> 5.0
        else -> 10.0
    }
    return nice * 10.0.pow(exponent)
}

private fun formatTick(v: Double): String =
    if (abs(v - v.roundToInt()) < 1e-6) v.roundToInt().toString() else "%.1f".format(v)
