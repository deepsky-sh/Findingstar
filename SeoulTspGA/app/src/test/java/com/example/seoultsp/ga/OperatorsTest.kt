package com.example.seoultsp.ga

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.random.Random

class OperatorsTest {

    private fun IntArray.isPermutation(): Boolean = sorted() == indices.toList()

    @Test
    fun orderCrossover_matchesTextbookExample() {
        // 부모1 = 1 2 3 | 4 5 6 7 | 8 9, 부모2 = 9 3 7 8 2 6 5 1 4 (값에서 1을 뺀 0-기반 표현)
        val p1 = intArrayOf(1, 2, 3, 4, 5, 6, 7, 8, 9).map { it - 1 }.toIntArray()
        val p2 = intArrayOf(9, 3, 7, 8, 2, 6, 5, 1, 4).map { it - 1 }.toIntArray()
        val child = Operators.orderCrossover(p1, p2, 3, 6)
        val expected = intArrayOf(3, 8, 2, 4, 5, 6, 7, 1, 9).map { it - 1 }.toIntArray()
        assertArrayEquals(expected, child)
    }

    @Test
    fun partiallyMappedCrossover_matchesTextbookExample() {
        val p1 = intArrayOf(1, 2, 3, 4, 5, 6, 7, 8, 9).map { it - 1 }.toIntArray()
        val p2 = intArrayOf(4, 5, 2, 1, 8, 7, 6, 9, 3).map { it - 1 }.toIntArray()
        val child = Operators.partiallyMappedCrossover(p1, p2, 3, 6)
        val expected = intArrayOf(1, 8, 2, 4, 5, 6, 7, 9, 3).map { it - 1 }.toIntArray()
        assertArrayEquals(expected, child)
    }

    @Test
    fun cycleCrossover_matchesTextbookExample() {
        val p1 = intArrayOf(1, 2, 3, 4, 5, 6, 7, 8).map { it - 1 }.toIntArray()
        val p2 = intArrayOf(8, 5, 2, 1, 3, 6, 4, 7).map { it - 1 }.toIntArray()
        val child = Operators.cycleCrossover(p1, p2)
        val expected = intArrayOf(1, 5, 2, 4, 3, 6, 7, 8).map { it - 1 }.toIntArray()
        assertArrayEquals(expected, child)
    }

    @Test
    fun everyCrossover_alwaysProducesValidPermutation() {
        val random = Random(7)
        repeat(2_000) {
            val n = 4 + random.nextInt(30)
            val p1 = IntArray(n) { it }.also { it.shuffle(random) }
            val p2 = IntArray(n) { it }.also { it.shuffle(random) }
            for (method in CrossoverMethod.entries) {
                val child = Operators.crossover(method, p1, p2, random)
                assertTrue("$method produced ${child.toList()}", child.isPermutation())
            }
        }
    }

    @Test
    fun everyMutation_alwaysProducesValidPermutation() {
        val random = Random(11)
        repeat(2_000) {
            val n = 4 + random.nextInt(30)
            for (method in MutationMethod.entries) {
                val tour = IntArray(n) { it }.also { it.shuffle(random) }
                Operators.mutate(method, tour, random)
                assertTrue("$method produced ${tour.toList()}", tour.isPermutation())
            }
        }
    }

    @Test
    fun swapMutation_changesExactlyTwoPositions() {
        val random = Random(3)
        repeat(200) {
            val original = IntArray(20) { it }
            val tour = original.copyOf()
            Operators.mutate(MutationMethod.Swap, tour, random)
            assertTrue(original.indices.count { original[it] != tour[it] } == 2)
        }
    }

    @Test
    fun insert_movesSingleGene() {
        val forward = intArrayOf(0, 1, 2, 3, 4, 5)
        Operators.insert(forward, 1, 4)
        assertArrayEquals(intArrayOf(0, 2, 3, 4, 1, 5), forward)

        val backward = intArrayOf(0, 1, 2, 3, 4, 5)
        Operators.insert(backward, 4, 1)
        assertArrayEquals(intArrayOf(0, 4, 1, 2, 3, 5), backward)
    }

    @Test
    fun randomSegment_returnsOrderedDistinctCutPoints() {
        val random = Random(5)
        repeat(1_000) {
            val (a, b) = Operators.randomSegment(20, random)
            assertTrue(a in 0 until b && b < 20)
        }
    }
}
