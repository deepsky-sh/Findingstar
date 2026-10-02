package com.example.seoultsp.sim

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableDoubleStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshots.SnapshotStateList
import com.example.seoultsp.ga.Attraction
import com.example.seoultsp.ga.DistanceMatrix
import com.example.seoultsp.ga.GaConfig
import com.example.seoultsp.ga.GenerationStats
import com.example.seoultsp.ga.GeneticAlgorithm
import com.example.seoultsp.ga.SeoulAttractions
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlin.random.Random

enum class SimStatus { Ready, Running, Paused, Finished }

/** 세대 사이의 대기 시간. [Max]는 한 프레임 예산 안에서 가능한 많은 세대를 계산합니다. */
enum class SimSpeed(val delayMillis: Long) { Slow(150), Normal(40), Fast(8), Max(0) }

/** 그래프에 그리는 세대별 값 (km). */
data class GenerationPoint(
    val generation: Int,
    val best: Double,
    val average: Double,
    val bestSoFar: Double,
)

/** 파라미터 비교를 위해 남겨 두는 직전 실행 기록. */
data class RunRecord(
    val config: GaConfig,
    val bestCurve: List<Double>,
    val finalCost: Double,
)

/**
 * 유전자 알고리즘 시뮬레이션의 상태와 실행을 관리합니다.
 *
 * 모든 상태는 Compose 스냅샷 상태라서 UI가 자동으로 갱신됩니다.
 * 계산은 [scope]의 디스패처(안드로이드에서는 메인 스레드)에서 프레임 예산 단위로 나누어 수행하므로
 * 별도의 동기화가 필요 없습니다. 도시 20개 규모에서는 한 세대가 1ms도 걸리지 않습니다.
 */
class SimulationController(
    private val scope: CoroutineScope,
    initialConfig: GaConfig = GaConfig(),
) {
    val attractions: List<Attraction> = SeoulAttractions.all
    private val distances = DistanceMatrix(attractions.map { it.location })

    var config: GaConfig by mutableStateOf(initialConfig.sanitized())
        private set
    var speed: SimSpeed by mutableStateOf(SimSpeed.Normal)
    var newSeedEachRun: Boolean by mutableStateOf(false)
    var status: SimStatus by mutableStateOf(SimStatus.Ready)
        private set

    /** 0세대부터 현재 세대까지의 기록. */
    val history: SnapshotStateList<GenerationPoint> = mutableStateListOf()

    /** 지금까지 찾은 가장 짧은 경로. 항상 0번(경복궁)에서 시작하도록 회전되어 있습니다. */
    var bestTour: List<Int> by mutableStateOf(emptyList())
        private set
    var bestCost: Double by mutableDoubleStateOf(0.0)
        private set
    var previousRun: RunRecord? by mutableStateOf(null)
        private set

    val canEditParameters: Boolean
        get() = status == SimStatus.Ready || status == SimStatus.Finished

    private var engine = GeneticAlgorithm(distances, config)
    private var loop: Job? = null

    init {
        rebuild()
    }

    /** 파라미터를 바꾸고 새 초기 개체군을 준비합니다. 실행 중이거나 일시정지 상태에서는 무시됩니다. */
    fun updateConfig(transform: (GaConfig) -> GaConfig) {
        if (!canEditParameters) return
        val next = transform(config).sanitized()
        if (next == config) return
        archiveIfProgressed()
        config = next
        rebuild()
    }

    fun restoreDefaults() = updateConfig { GaConfig() }

    fun rerollSeed() = updateConfig { it.copy(seed = randomSeed()) }

    /** 시작 / 일시정지 / 계속 / 다시 실행을 상태에 맞게 수행합니다. */
    fun playPause() {
        when (status) {
            SimStatus.Ready, SimStatus.Paused -> run()
            SimStatus.Running -> pause()
            SimStatus.Finished -> {
                reset()
                run()
            }
        }
    }

    fun pause() {
        loop?.cancel()
        loop = null
        if (status == SimStatus.Running) status = SimStatus.Paused
    }

    /** 한 세대만 진행합니다. */
    fun stepOnce() {
        if (status != SimStatus.Ready && status != SimStatus.Paused) return
        publish(listOf(engine.step()))
        status = if (engine.isFinished) SimStatus.Finished else SimStatus.Paused
    }

    /** 현재 실행을 비교용 기록으로 남기고 0세대로 되돌립니다. */
    fun reset() {
        archiveIfProgressed()
        if (newSeedEachRun) config = config.copy(seed = randomSeed())
        rebuild()
    }

    private fun run() {
        status = SimStatus.Running
        loop?.cancel()
        loop = scope.launch {
            while (isActive && status == SimStatus.Running) {
                val budgetNanos = if (speed == SimSpeed.Max) FRAME_BUDGET_NANOS else 0L
                val started = System.nanoTime()
                val batch = ArrayList<GenerationStats>()
                do {
                    batch += engine.step()
                } while (!engine.isFinished && System.nanoTime() - started < budgetNanos)
                publish(batch)
                if (engine.isFinished) {
                    status = SimStatus.Finished
                    break
                }
                delay(if (speed == SimSpeed.Max) FRAME_MILLIS else speed.delayMillis)
            }
        }
    }

    private fun rebuild() {
        loop?.cancel()
        loop = null
        engine = GeneticAlgorithm(distances, config)
        history.clear()
        bestTour = emptyList()
        publish(listOf(engine.stats()))
        status = SimStatus.Ready
    }

    private fun archiveIfProgressed() {
        if (history.size > 1) {
            previousRun = RunRecord(
                config = engine.config,
                bestCurve = history.map { it.best },
                finalCost = bestCost,
            )
        }
    }

    private fun publish(batch: List<GenerationStats>) {
        if (batch.isEmpty()) return
        history.addAll(
            batch.map { GenerationPoint(it.generation, it.bestCost, it.averageCost, it.bestSoFarCost) },
        )
        val last = batch.last()
        if (bestTour.isEmpty() || last.bestSoFarCost < bestCost) {
            bestCost = last.bestSoFarCost
            bestTour = normalizeTour(last.bestSoFarTour)
        }
    }

    companion object {
        private const val FRAME_BUDGET_NANOS = 8_000_000L
        private const val FRAME_MILLIS = 16L

        private fun randomSeed(): Long = Random.nextLong(1, 100_000)

        /** 순회 경로를 0번 도시에서 시작하고, 두 번째 도시 번호가 마지막 도시 번호보다 작은 방향으로 맞춥니다. */
        fun normalizeTour(tour: List<Int>): List<Int> {
            if (tour.isEmpty()) return tour
            val start = tour.indexOf(0).coerceAtLeast(0)
            val rotated = tour.drop(start) + tour.take(start)
            return if (rotated.size > 2 && rotated[1] > rotated.last()) {
                listOf(rotated.first()) + rotated.drop(1).reversed()
            } else {
                rotated
            }
        }
    }
}
