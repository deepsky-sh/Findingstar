package com.example.seoultsp.ga

import kotlin.random.Random

/** 한 세대가 끝난 시점의 요약 통계. 거리 단위는 km. */
data class GenerationStats(
    val generation: Int,
    /** 이번 세대에서 가장 짧은 경로. */
    val bestCost: Double,
    val averageCost: Double,
    val worstCost: Double,
    /** 0세대부터 지금까지 찾은 가장 짧은 경로. */
    val bestSoFarCost: Double,
    val bestSoFarTour: List<Int>,
)

/**
 * 순회 세일즈맨 문제(TSP)를 푸는 세대 교체형 유전자 알고리즘.
 *
 * 개체 하나는 도시 방문 순서를 나타내는 순열이며, 적합도는 순회 거리가 짧을수록 높습니다.
 * 한 세대는 엘리트 보존 → 선택 → 교차 → 돌연변이 → 평가 순서로 진행됩니다.
 * 같은 [GaConfig.seed]를 쓰면 항상 같은 결과가 나옵니다.
 */
class GeneticAlgorithm(
    private val distances: DistanceMatrix,
    config: GaConfig,
) {
    val config: GaConfig = config.sanitized()

    private val random = Random(this.config.seed)
    private val cityCount = distances.size

    private var population: Array<IntArray>
    private var costs: DoubleArray

    var generation: Int = 0
        private set

    private var bestSoFarTour: IntArray
    var bestSoFarCost: Double
        private set

    val isFinished: Boolean get() = generation >= config.generations

    init {
        require(cityCount >= 4) { "도시가 4개 이상이어야 합니다." }
        population = Array(this.config.populationSize) { randomTour() }
        costs = DoubleArray(population.size) { distances.tourLength(population[it]) }
        val best = indexOfBest()
        bestSoFarTour = population[best].copyOf()
        bestSoFarCost = costs[best]
    }

    /** 현재 개체군의 통계. 0세대(초기 무작위 개체군)도 이 함수로 얻습니다. */
    fun stats(): GenerationStats {
        var best = Double.MAX_VALUE
        var worst = 0.0
        var sum = 0.0
        for (c in costs) {
            if (c < best) best = c
            if (c > worst) worst = c
            sum += c
        }
        return GenerationStats(
            generation = generation,
            bestCost = best,
            averageCost = sum / costs.size,
            worstCost = worst,
            bestSoFarCost = bestSoFarCost,
            bestSoFarTour = bestSoFarTour.toList(),
        )
    }

    /** 한 세대를 진행하고 새 세대의 통계를 돌려줍니다. */
    fun step(): GenerationStats {
        val size = population.size
        val ranked = population.indices.sortedBy { costs[it] }
        val next = ArrayList<IntArray>(size)

        for (i in 0 until minOf(config.eliteCount, size)) {
            next += population[ranked[i]].copyOf()
        }

        val select = selector(ranked)
        while (next.size < size) {
            val parent1 = population[select()]
            val parent2 = population[select()]
            val child1: IntArray
            val child2: IntArray
            if (random.nextDouble() < config.crossoverRate) {
                child1 = Operators.crossover(config.crossover, parent1, parent2, random)
                child2 = Operators.crossover(config.crossover, parent2, parent1, random)
            } else {
                child1 = parent1.copyOf()
                child2 = parent2.copyOf()
            }
            if (random.nextDouble() < config.mutationRate) Operators.mutate(config.mutation, child1, random)
            if (random.nextDouble() < config.mutationRate) Operators.mutate(config.mutation, child2, random)
            next += child1
            if (next.size < size) next += child2
        }

        population = next.toTypedArray()
        costs = DoubleArray(size) { distances.tourLength(population[it]) }
        generation++

        val best = indexOfBest()
        if (costs[best] < bestSoFarCost) {
            bestSoFarCost = costs[best]
            bestSoFarTour = population[best].copyOf()
        }
        return stats()
    }

    /** 이번 세대에서 부모 한 개체의 인덱스를 고르는 함수를 만듭니다. [ranked]는 거리 오름차순 인덱스. */
    private fun selector(ranked: List<Int>): () -> Int {
        val size = population.size
        return when (config.selection) {
            SelectionMethod.Tournament -> {
                {
                    var winner = random.nextInt(size)
                    repeat(config.tournamentSize - 1) {
                        val challenger = random.nextInt(size)
                        if (costs[challenger] < costs[winner]) winner = challenger
                    }
                    winner
                }
            }
            SelectionMethod.Roulette -> {
                // 최소화 문제이므로 (최악 거리 − 거리)를 적합도로 써서 짧은 경로일수록 넓은 칸을 차지하게 합니다.
                val worst = costs[ranked.last()]
                val weights = DoubleArray(size) { worst - costs[it] }
                weightedSelector(weights) { it }
            }
            SelectionMethod.Rank -> {
                // 1등은 size, 꼴찌는 1의 가중치 (선형 순위 선택).
                val weights = DoubleArray(size) { rank -> (size - rank).toDouble() }
                weightedSelector(weights) { ranked[it] }
            }
        }
    }

    private fun weightedSelector(weights: DoubleArray, mapIndex: (Int) -> Int): () -> Int {
        val cumulative = DoubleArray(weights.size)
        var total = 0.0
        for (i in weights.indices) {
            total += weights[i]
            cumulative[i] = total
        }
        if (total <= 0.0) {
            // 모든 개체의 거리가 같으면 균등하게 고릅니다.
            return { mapIndex(random.nextInt(weights.size)) }
        }
        return {
            val target = random.nextDouble() * total
            var index = cumulative.binarySearch(target)
            if (index < 0) index = -index - 1
            mapIndex(index.coerceAtMost(weights.size - 1))
        }
    }

    private fun indexOfBest(): Int {
        var best = 0
        for (i in 1 until costs.size) if (costs[i] < costs[best]) best = i
        return best
    }

    private fun randomTour(): IntArray = IntArray(cityCount) { it }.also { tour ->
        for (i in tour.size - 1 downTo 1) {
            val j = random.nextInt(i + 1)
            val t = tour[i]
            tour[i] = tour[j]
            tour[j] = t
        }
    }
}
