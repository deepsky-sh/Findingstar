package com.example.seoultsp.ga

import kotlin.random.Random

/**
 * 순열(경로) 표현에 쓰는 교차·돌연변이 연산자.
 * 모든 연산자는 입력을 변경하지 않거나(교차) 주어진 배열만 변경하며(돌연변이), 결과는 항상 올바른 순열입니다.
 */
object Operators {

    // ---------------------------------------------------------------- 교차

    fun crossover(method: CrossoverMethod, p1: IntArray, p2: IntArray, random: Random): IntArray {
        return when (method) {
            CrossoverMethod.OX -> {
                val (a, b) = randomSegment(p1.size, random)
                orderCrossover(p1, p2, a, b)
            }
            CrossoverMethod.PMX -> {
                val (a, b) = randomSegment(p1.size, random)
                partiallyMappedCrossover(p1, p2, a, b)
            }
            CrossoverMethod.CX -> cycleCrossover(p1, p2)
        }
    }

    /** 순서 교차: p1의 [start..end] 구간을 그대로 두고, 나머지는 p2의 등장 순서대로 채웁니다. */
    fun orderCrossover(p1: IntArray, p2: IntArray, start: Int, end: Int): IntArray {
        val n = p1.size
        val child = IntArray(n) { -1 }
        val used = BooleanArray(n)
        for (i in start..end) {
            child[i] = p1[i]
            used[p1[i]] = true
        }
        var write = (end + 1) % n
        for (k in 0 until n) {
            val gene = p2[(end + 1 + k) % n]
            if (!used[gene]) {
                child[write] = gene
                used[gene] = true
                write = (write + 1) % n
            }
        }
        return child
    }

    /** 부분 매핑 교차: p1의 구간을 복사하고, p2 구간의 값들은 매핑 관계를 따라 빈 자리로 보냅니다. */
    fun partiallyMappedCrossover(p1: IntArray, p2: IntArray, start: Int, end: Int): IntArray {
        val n = p1.size
        val child = IntArray(n) { -1 }
        val inSegment = BooleanArray(n)
        val positionInP2 = IntArray(n)
        for (i in 0 until n) positionInP2[p2[i]] = i
        for (i in start..end) {
            child[i] = p1[i]
            inSegment[p1[i]] = true
        }
        for (i in start..end) {
            val gene = p2[i]
            if (inSegment[gene]) continue
            var pos = i
            do {
                pos = positionInP2[p1[pos]]
            } while (pos in start..end)
            child[pos] = gene
        }
        for (i in 0 until n) {
            if (child[i] == -1) child[i] = p2[i]
        }
        return child
    }

    /** 사이클 교차: 위치 사이클을 찾아 홀수 번째 사이클은 p1, 짝수 번째는 p2에서 물려받습니다. */
    fun cycleCrossover(p1: IntArray, p2: IntArray): IntArray {
        val n = p1.size
        val child = IntArray(n) { -1 }
        val positionInP1 = IntArray(n)
        for (i in 0 until n) positionInP1[p1[i]] = i
        var cycle = 0
        for (startPos in 0 until n) {
            if (child[startPos] != -1) continue
            val source = if (cycle % 2 == 0) p1 else p2
            var pos = startPos
            do {
                child[pos] = source[pos]
                pos = positionInP1[p2[pos]]
            } while (pos != startPos)
            cycle++
        }
        return child
    }

    // ---------------------------------------------------------------- 돌연변이

    fun mutate(method: MutationMethod, tour: IntArray, random: Random) {
        when (method) {
            MutationMethod.Swap -> {
                val i = random.nextInt(tour.size)
                var j = random.nextInt(tour.size - 1)
                if (j >= i) j++
                swap(tour, i, j)
            }
            MutationMethod.Inversion -> {
                val (a, b) = randomSegment(tour.size, random)
                reverse(tour, a, b)
            }
            MutationMethod.Scramble -> {
                val (a, b) = randomSegment(tour.size, random)
                for (i in b downTo a + 1) {
                    swap(tour, i, a + random.nextInt(i - a + 1))
                }
            }
            MutationMethod.Insertion -> {
                val from = random.nextInt(tour.size)
                var to = random.nextInt(tour.size - 1)
                if (to >= from) to++
                insert(tour, from, to)
            }
        }
    }

    fun reverse(tour: IntArray, start: Int, end: Int) {
        var i = start
        var j = end
        while (i < j) swap(tour, i++, j--)
    }

    /** [from] 위치의 값을 꺼내 [to] 위치로 옮기고 사이 값들을 한 칸씩 민다. */
    fun insert(tour: IntArray, from: Int, to: Int) {
        val gene = tour[from]
        if (from < to) {
            System.arraycopy(tour, from + 1, tour, from, to - from)
        } else if (from > to) {
            System.arraycopy(tour, to, tour, to + 1, from - to)
        }
        tour[to] = gene
    }

    /** 0 ≤ a < b < size 인 서로 다른 두 절단점. */
    fun randomSegment(size: Int, random: Random): Pair<Int, Int> {
        val a = random.nextInt(size)
        var b = random.nextInt(size - 1)
        if (b >= a) b++
        return if (a < b) a to b else b to a
    }

    private fun swap(tour: IntArray, i: Int, j: Int) {
        val t = tour[i]
        tour[i] = tour[j]
        tour[j] = t
    }
}
