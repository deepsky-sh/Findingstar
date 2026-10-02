package com.example.seoultsp.ga

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class GeneticAlgorithmTest {

    private val distances = DistanceMatrix(SeoulAttractions.all.map { it.location })

    private fun run(config: GaConfig): GeneticAlgorithm =
        GeneticAlgorithm(distances, config).also { ga -> while (!ga.isFinished) ga.step() }

    @Test
    fun distanceMatrix_isSymmetricWithZeroDiagonal() {
        for (i in 0 until distances.size) {
            assertEquals(0.0, distances[i, i], 1e-12)
            for (j in 0 until distances.size) {
                assertEquals(distances[i, j], distances[j, i], 1e-12)
            }
        }
    }

    @Test
    fun haversine_matchesKnownDistance() {
        // 경복궁 ↔ 롯데월드타워는 직선으로 약 13km 떨어져 있습니다.
        val km = distances[0, 18]
        assertTrue("was $km", km in 12.5..14.0)
    }

    @Test
    fun optimalTour_isValidAndMatchesConstant() {
        val tour = SeoulAttractions.optimalTour
        assertEquals(SeoulAttractions.all.indices.toList(), tour.sorted())
        assertEquals(SeoulAttractions.OPTIMAL_TOUR_KM, distances.tourLength(tour), 1e-6)
    }

    @Test
    fun sameSeed_givesIdenticalRuns() {
        val config = GaConfig(generations = 120, seed = 99)
        assertEquals(run(config).stats(), run(config).stats())
    }

    @Test
    fun elitism_neverLosesTheBestTour() {
        for (selection in SelectionMethod.entries) {
            val ga = GeneticAlgorithm(distances, GaConfig(selection = selection, eliteCount = 1, seed = 5))
            var previous = ga.stats().bestCost
            repeat(150) {
                val best = ga.step().bestCost
                assertTrue("$selection got worse: $previous -> $best", best <= previous + 1e-9)
                previous = best
            }
        }
    }

    @Test
    fun bestSoFarTour_isConsistentWithReportedCost() {
        val ga = GeneticAlgorithm(distances, GaConfig(eliteCount = 0, mutationRate = 0.6, seed = 17))
        repeat(80) {
            val stats = ga.step()
            assertEquals(stats.bestSoFarCost, distances.tourLength(stats.bestSoFarTour), 1e-9)
            assertTrue(stats.bestSoFarCost <= stats.bestCost + 1e-9)
            assertTrue(stats.bestCost <= stats.averageCost && stats.averageCost <= stats.worstCost)
        }
    }

    @Test
    fun defaultConfig_convergesCloseToOptimum() {
        val ga = GeneticAlgorithm(distances, GaConfig())
        val initial = ga.stats().bestCost
        while (!ga.isFinished) ga.step()
        val final = ga.bestSoFarCost
        assertTrue("no real improvement: $initial -> $final", final < initial * 0.6)
        assertTrue("too far from optimum: $final", final <= SeoulAttractions.OPTIMAL_TOUR_KM * 1.05)
    }

    @Test
    fun everyOperatorCombination_improvesOnRandomTours() {
        for (selection in SelectionMethod.entries) {
            for (crossover in CrossoverMethod.entries) {
                for (mutation in MutationMethod.entries) {
                    val config = GaConfig(
                        generations = 150,
                        selection = selection,
                        crossover = crossover,
                        mutation = mutation,
                        seed = 3,
                    )
                    val ga = GeneticAlgorithm(distances, config)
                    val initial = ga.stats().bestCost
                    while (!ga.isFinished) ga.step()
                    assertTrue(
                        "$selection/$crossover/$mutation: $initial -> ${ga.bestSoFarCost}",
                        ga.bestSoFarCost < initial * 0.85,
                    )
                }
            }
        }
    }

    @Test
    fun sanitized_clampsOutOfRangeValues() {
        val config = GaConfig(
            populationSize = 5,
            generations = 1,
            crossoverRate = 1.5,
            mutationRate = -1.0,
            eliteCount = 99,
            tournamentSize = 99,
        ).sanitized()
        assertEquals(GaConfig.POPULATION_RANGE.first, config.populationSize)
        assertEquals(GaConfig.GENERATION_RANGE.first, config.generations)
        assertEquals(1.0, config.crossoverRate, 0.0)
        assertEquals(0.0, config.mutationRate, 0.0)
        assertEquals(GaConfig.ELITE_RANGE.last, config.eliteCount)
        assertEquals(GaConfig.TOURNAMENT_RANGE.last, config.tournamentSize)
    }
}
