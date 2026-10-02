package com.example.seoultsp.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.calculateCentroid
import androidx.compose.foundation.gestures.calculatePan
import androidx.compose.foundation.gestures.calculateZoom
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
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
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.pointer.positionChanged
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import com.example.seoultsp.ga.Attraction
import com.example.seoultsp.ga.DistanceMatrix
import com.example.seoultsp.ga.GeoPoint
import com.example.seoultsp.ga.SeoulAttractions
import com.example.seoultsp.ui.theme.LocalExtraColors
import com.example.seoultsp.ui.theme.TabularNumbers
import kotlin.math.cos
import kotlin.math.hypot

/** 위경도를 화면 좌표로 바꾸는 등장방형 투영. 서울 정도의 좁은 범위에서는 왜곡이 거의 없습니다. */
private class MapProjection(points: List<GeoPoint>, marginKm: Double) {
    private val kmPerLon: Double
    private val kmPerLat = 110.574
    private val minX: Double
    private val maxY: Double
    val widthKm: Double
    val heightKm: Double

    init {
        kmPerLon = 111.320 * cos(Math.toRadians(points.map { it.latitude }.average()))
        val xs = points.map { it.longitude * kmPerLon }
        val ys = points.map { it.latitude * kmPerLat }
        minX = xs.min() - marginKm
        maxY = ys.max() + marginKm
        widthKm = xs.max() + marginKm - minX
        heightKm = maxY - (ys.min() - marginKm)
    }

    val aspectRatio: Float get() = (widthKm / heightKm).toFloat()

    fun project(p: GeoPoint, size: Size): Offset {
        val pxPerKm = size.width / widthKm
        return Offset(
            ((p.longitude * kmPerLon - minX) * pxPerKm).toFloat(),
            ((maxY - p.latitude * kmPerLat) * pxPerKm).toFloat(),
        )
    }

    fun kmToPx(km: Double, size: Size): Float = (km * size.width / widthKm).toFloat()
}

/** 지도 카드: 경로 지도 + 방문 순서 칩. */
@Composable
fun RouteMapCard(
    attractions: List<Attraction>,
    tour: List<Int>,
    cost: Double,
    selected: Int?,
    onSelect: (Int?) -> Unit,
    modifier: Modifier = Modifier,
) {
    SectionCard(
        title = "최단 경로 지도",
        subtitle = "지금까지 찾은 가장 짧은 순회 경로",
        modifier = modifier,
        trailing = {
            Text(
                text = formatKm(cost) + " km",
                style = MaterialTheme.typography.titleMedium.merge(TabularNumbers),
                color = MaterialTheme.colorScheme.primary,
            )
        },
    ) {
        RouteMap(attractions, tour, selected, onSelect)
        Spacer(Modifier.height(8.dp))
        Text(
            "두 손가락으로 확대 · 두 번 탭하면 원래대로",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(16.dp))
        RouteSequence(attractions, tour, selected, onSelect)
    }
}

@Composable
fun RouteMap(
    attractions: List<Attraction>,
    tour: List<Int>,
    selected: Int?,
    onSelect: (Int?) -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = MaterialTheme.colorScheme
    val extra = LocalExtraColors.current
    val projection = remember(attractions) { MapProjection(attractions.map { it.location }, marginKm = 1.3) }
    val textMeasurer = rememberTextMeasurer()
    val labelStyle = MaterialTheme.typography.labelSmall.copy(color = colors.onSurface)
    val selectedStyle = labelStyle.copy(fontWeight = FontWeight.Bold, color = colors.onPrimaryContainer)
    val riverStyle = labelStyle.copy(color = extra.river, fontStyle = FontStyle.Italic, fontWeight = FontWeight.Bold)
    val labels = remember(attractions, labelStyle) {
        attractions.map { textMeasurer.measure(AnnotatedString(it.name), style = labelStyle) }
    }
    val selectedLabels = remember(attractions, selectedStyle) {
        attractions.map { textMeasurer.measure(AnnotatedString(it.name), style = selectedStyle) }
    }
    val riverLabel = remember(riverStyle) { textMeasurer.measure(AnnotatedString("한강"), style = riverStyle) }
    // 주변에 다른 관광지가 없는 곳부터 이름표를 배치하면 밀집 지역에서도 이름이 고르게 보입니다.
    val labelPriority = remember(attractions) {
        attractions.indices.sortedByDescending { i ->
            attractions.indices.filter { it != i }.minOf { j ->
                DistanceMatrix.haversineKm(attractions[i].location, attractions[j].location)
            }
        }
    }

    var zoom by remember { mutableFloatStateOf(1f) }
    var pan by remember { mutableStateOf(Offset.Zero) }
    val currentOnSelect by rememberUpdatedState(onSelect)
    val currentSelected by rememberUpdatedState(selected)

    Canvas(
        modifier = modifier
            .fillMaxWidth()
            .aspectRatio(projection.aspectRatio)
            .clip(RoundedCornerShape(18.dp))
            .background(extra.mapBackground)
            .pointerInput(projection) {
                // 두 손가락으로 확대/이동. 확대하지 않은 상태의 한 손가락 드래그는 화면 스크롤에 양보합니다.
                awaitEachGesture {
                    awaitFirstDown(requireUnconsumed = false)
                    do {
                        val event = awaitPointerEvent()
                        val pressed = event.changes.count { it.pressed }
                        if (pressed >= 2 || zoom > 1.01f) {
                            val zoomChange = event.calculateZoom()
                            val panChange = event.calculatePan()
                            val centroid = event.calculateCentroid(useCurrent = true)
                            if (centroid != Offset.Unspecified) {
                                val newZoom = (zoom * zoomChange).coerceIn(1f, 6f)
                                val scaled = centroid - (centroid - pan) * (newZoom / zoom) + panChange
                                zoom = newZoom
                                pan = clampPan(scaled, newZoom, Size(size.width.toFloat(), size.height.toFloat()))
                            }
                            event.changes.forEach { if (it.positionChanged()) it.consume() }
                        }
                    } while (event.changes.any { it.pressed })
                }
            }
            .pointerInput(projection, attractions) {
                detectTapGestures(
                    onDoubleTap = {
                        zoom = 1f
                        pan = Offset.Zero
                    },
                    onTap = { tap ->
                        val canvas = Size(size.width.toFloat(), size.height.toFloat())
                        val hit = attractions.minByOrNull { a ->
                            val p = projection.project(a.location, canvas) * zoom + pan
                            hypot(p.x - tap.x, p.y - tap.y)
                        }
                        val hitDistance = hit?.let { a ->
                            val p = projection.project(a.location, canvas) * zoom + pan
                            hypot(p.x - tap.x, p.y - tap.y)
                        } ?: Float.MAX_VALUE
                        val id = if (hitDistance < 28.dp.toPx()) hit?.id else null
                        currentOnSelect(if (id == currentSelected) null else id)
                    },
                )
            },
    ) {
        fun toScreen(p: GeoPoint): Offset = projection.project(p, size) * zoom + pan

        drawGrid(projection.kmToPx(2.0, size) * zoom, pan, extra.mapGrid)

        // 한강
        val river = SeoulAttractions.hanRiver.map(::toScreen)
        drawPath(
            path = smoothPath(river),
            color = extra.river.copy(alpha = 0.55f),
            style = Stroke(width = 11.dp.toPx() * kotlin.math.sqrt(zoom), cap = StrokeCap.Round, join = StrokeJoin.Round),
        )
        // 경로가 지나지 않는 북동쪽 강변에 강 이름을 둡니다.
        val riverAnchor = toScreen(GeoPoint(37.552, 127.119))
        val riverLabelTopLeft = riverAnchor - Offset(riverLabel.size.width.toFloat(), riverLabel.size.height / 2f)
        drawText(riverLabel, topLeft = riverLabelTopLeft)

        val points = attractions.map { toScreen(it.location) }

        // 경로
        if (tour.size == attractions.size) {
            val route = Path().apply {
                moveTo(points[tour[0]].x, points[tour[0]].y)
                for (k in 1 until tour.size) lineTo(points[tour[k]].x, points[tour[k]].y)
                close()
            }
            drawPath(route, colors.primary.copy(alpha = 0.16f), style = Stroke(8.dp.toPx(), join = StrokeJoin.Round))
            drawPath(route, colors.primary, style = Stroke(2.4.dp.toPx(), join = StrokeJoin.Round))
            for (k in tour.indices) {
                drawDirectionArrow(points[tour[k]], points[tour[(k + 1) % tour.size]], colors.primary)
            }
        }

        // 관광지 점
        val nodeRadius = 5.5.dp.toPx()
        val startId = tour.firstOrNull()
        attractions.forEach { a ->
            val p = points[a.id]
            if (a.id == selected) {
                drawCircle(colors.tertiary.copy(alpha = 0.3f), radius = 14.dp.toPx(), center = p)
                drawCircle(colors.tertiary, radius = 14.dp.toPx(), center = p, style = Stroke(2.dp.toPx()))
            }
            if (a.id == startId) {
                drawCircle(colors.surface, radius = nodeRadius + 4.dp.toPx(), center = p)
                drawCircle(colors.primary, radius = nodeRadius + 2.5.dp.toPx(), center = p)
                drawCircle(colors.onPrimary, radius = 2.5.dp.toPx(), center = p)
            } else {
                drawCircle(colors.surface, radius = nodeRadius, center = p)
                drawCircle(colors.primary, radius = nodeRadius, center = p, style = Stroke(2.dp.toPx()))
            }
        }

        // 이름표: 겹치지 않는 자리에만 배치
        val placed = arrayListOf(Rect(riverLabelTopLeft, Size(riverLabel.size.width.toFloat(), riverLabel.size.height.toFloat())))
        val nodeBoxes = points.map { Rect(it, nodeRadius + 2.dp.toPx()) }
        val order = listOfNotNull(selected, startId) + labelPriority.filter { it != selected && it != startId }
        val gap = 4.dp.toPx()
        val padH = 4.dp.toPx()
        val padV = 1.5.dp.toPx()
        val bounds = Rect(Offset.Zero, size)
        for (id in order) {
            val layout = if (id == selected) selectedLabels[id] else labels[id]
            val w = layout.size.width + padH * 2
            val h = layout.size.height + padV * 2
            val p = points[id]
            val r = nodeRadius + gap + if (id == startId) 3.dp.toPx() else 0f
            val d = r * 0.7f
            val candidates = listOf(
                Offset(p.x + r, p.y - h / 2),
                Offset(p.x - r - w, p.y - h / 2),
                Offset(p.x - w / 2, p.y - r - h),
                Offset(p.x - w / 2, p.y + r),
                Offset(p.x + d, p.y - d - h),
                Offset(p.x + d, p.y + d),
                Offset(p.x - d - w, p.y - d - h),
                Offset(p.x - d - w, p.y + d),
            ).map { Rect(it, Size(w, h)) }
            fun Rect.inBounds() = left >= bounds.left && top >= bounds.top && right <= bounds.right && bottom <= bounds.bottom
            fun Rect.isFree() = placed.none { it.overlaps(this) } &&
                nodeBoxes.withIndex().none { (j, box) -> j != id && box.overlaps(this) }
            val spot = candidates.firstOrNull { it.inBounds() && it.isFree() }
                // 선택한 관광지의 이름은 다른 점을 조금 가리더라도 항상 보여 줍니다.
                ?: (if (id == selected) candidates.firstOrNull { it.inBounds() } else null)
                ?: continue
            placed += spot
            drawRoundRect(
                color = if (id == selected) colors.primaryContainer else colors.surface.copy(alpha = 0.88f),
                topLeft = spot.topLeft,
                size = spot.size,
                cornerRadius = CornerRadius(5.dp.toPx()),
            )
            drawText(layout, topLeft = Offset(spot.left + padH, spot.top + padV))
        }
    }
}

private fun clampPan(pan: Offset, zoom: Float, size: Size): Offset = Offset(
    pan.x.coerceIn(size.width * (1 - zoom), 0f),
    pan.y.coerceIn(size.height * (1 - zoom), 0f),
)

private fun DrawScope.drawGrid(step: Float, pan: Offset, color: Color) {
    if (step < 4f) return
    var x = pan.x % step
    if (x < 0) x += step
    while (x < size.width) {
        drawLine(color, Offset(x, 0f), Offset(x, size.height), strokeWidth = 1.dp.toPx())
        x += step
    }
    var y = pan.y % step
    if (y < 0) y += step
    while (y < size.height) {
        drawLine(color, Offset(0f, y), Offset(size.width, y), strokeWidth = 1.dp.toPx())
        y += step
    }
}

/** 구간 중앙에 진행 방향을 나타내는 작은 화살표. 너무 짧은 구간은 생략합니다. */
private fun DrawScope.drawDirectionArrow(from: Offset, to: Offset, color: Color) {
    val dx = to.x - from.x
    val dy = to.y - from.y
    val length = hypot(dx, dy)
    if (length < 30.dp.toPx()) return
    val ux = dx / length
    val uy = dy / length
    val mid = Offset(from.x + dx / 2, from.y + dy / 2)
    val s = 4.dp.toPx()
    val tip = Offset(mid.x + ux * s, mid.y + uy * s)
    val back = Offset(mid.x - ux * s, mid.y - uy * s)
    val normal = Offset(-uy * s, ux * s)
    val arrow = Path().apply {
        moveTo(back.x + normal.x, back.y + normal.y)
        lineTo(tip.x, tip.y)
        lineTo(back.x - normal.x, back.y - normal.y)
    }
    drawPath(arrow, color, style = Stroke(2.dp.toPx(), cap = StrokeCap.Round, join = StrokeJoin.Round))
}

/** Catmull-Rom 스플라인으로 점들을 부드럽게 잇는 경로. */
private fun smoothPath(points: List<Offset>): Path = Path().apply {
    if (points.isEmpty()) return@apply
    moveTo(points[0].x, points[0].y)
    for (i in 0 until points.size - 1) {
        val p0 = points[maxOf(i - 1, 0)]
        val p1 = points[i]
        val p2 = points[i + 1]
        val p3 = points[minOf(i + 2, points.size - 1)]
        cubicTo(
            p1.x + (p2.x - p0.x) / 6f, p1.y + (p2.y - p0.y) / 6f,
            p2.x - (p3.x - p1.x) / 6f, p2.y - (p3.y - p1.y) / 6f,
            p2.x, p2.y,
        )
    }
}

/** 방문 순서를 번호가 붙은 칩으로 보여 줍니다. 칩을 누르면 지도에서 강조됩니다. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun RouteSequence(
    attractions: List<Attraction>,
    tour: List<Int>,
    selected: Int?,
    onSelect: (Int?) -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = MaterialTheme.colorScheme
    Column(modifier) {
        Text(
            "방문 순서",
            style = MaterialTheme.typography.labelLarge,
            color = colors.onSurfaceVariant,
        )
        Spacer(Modifier.height(8.dp))
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            tour.forEachIndexed { index, id ->
                StopChip(
                    number = (index + 1).toString(),
                    name = attractions[id].name,
                    isStart = index == 0,
                    isSelected = id == selected,
                    onClick = { onSelect(if (id == selected) null else id) },
                )
            }
            if (tour.isNotEmpty()) {
                StopChip(
                    number = "↩",
                    name = attractions[tour.first()].name + " 도착",
                    isStart = true,
                    isSelected = false,
                    onClick = { onSelect(tour.first()) },
                )
            }
        }
    }
}

@Composable
private fun StopChip(number: String, name: String, isStart: Boolean, isSelected: Boolean, onClick: () -> Unit) {
    val colors = MaterialTheme.colorScheme
    Row(
        modifier = Modifier
            .clip(CircleShape)
            .background(if (isSelected) colors.tertiaryContainer else colors.surfaceVariant)
            .clickable(onClick = onClick)
            .padding(start = 3.dp, end = 10.dp, top = 3.dp, bottom = 3.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(22.dp)
                .clip(CircleShape)
                .background(if (isStart) colors.primary else colors.surface),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                number,
                style = MaterialTheme.typography.labelSmall.merge(TabularNumbers),
                color = if (isStart) colors.onPrimary else colors.primary,
            )
        }
        Spacer(Modifier.width(6.dp))
        Text(
            name,
            style = MaterialTheme.typography.labelMedium,
            color = if (isSelected) colors.onTertiaryContainer else colors.onSurface,
        )
    }
}
