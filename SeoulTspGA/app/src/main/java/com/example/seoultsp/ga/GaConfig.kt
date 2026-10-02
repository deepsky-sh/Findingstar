package com.example.seoultsp.ga

enum class SelectionMethod { Tournament, Roulette, Rank }

enum class CrossoverMethod { OX, PMX, CX }

enum class MutationMethod { Swap, Inversion, Scramble, Insertion }

/** 유전자 알고리즘의 모든 조정 가능한 인자. */
data class GaConfig(
    val populationSize: Int = 80,
    val generations: Int = 300,
    val crossoverRate: Double = 0.9,
    val mutationRate: Double = 0.2,
    val eliteCount: Int = 2,
    val selection: SelectionMethod = SelectionMethod.Tournament,
    val tournamentSize: Int = 4,
    val crossover: CrossoverMethod = CrossoverMethod.OX,
    val mutation: MutationMethod = MutationMethod.Inversion,
    val seed: Long = 212L,
) {
    /** 범위를 벗어난 값을 허용 범위 안으로 맞춘 사본. */
    fun sanitized(): GaConfig {
        val population = populationSize.coerceIn(POPULATION_RANGE)
        return copy(
            populationSize = population,
            generations = generations.coerceIn(GENERATION_RANGE),
            crossoverRate = crossoverRate.coerceIn(0.0, 1.0),
            mutationRate = mutationRate.coerceIn(0.0, 1.0),
            eliteCount = eliteCount.coerceIn(0, minOf(ELITE_RANGE.last, population - 1)),
            tournamentSize = tournamentSize.coerceIn(TOURNAMENT_RANGE.first, minOf(TOURNAMENT_RANGE.last, population)),
        )
    }

    companion object {
        val POPULATION_RANGE = 20..500
        val GENERATION_RANGE = 50..2000
        val ELITE_RANGE = 0..10
        val TOURNAMENT_RANGE = 2..10
    }
}
