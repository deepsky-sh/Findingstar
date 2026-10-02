package com.example.seoultsp.ga

import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

/** 관광지 사이의 직선 거리(km)를 미리 계산해 둔 대칭 행렬. */
class DistanceMatrix(points: List<GeoPoint>) {

    val size: Int = points.size

    private val km: Array<DoubleArray> = Array(size) { i ->
        DoubleArray(size) { j -> haversineKm(points[i], points[j]) }
    }

    operator fun get(from: Int, to: Int): Double = km[from][to]

    /** 마지막 도시에서 첫 도시로 돌아오는 구간까지 포함한 순회 거리. */
    fun tourLength(tour: IntArray): Double {
        var total = 0.0
        for (k in tour.indices) {
            total += km[tour[k]][tour[(k + 1) % tour.size]]
        }
        return total
    }

    fun tourLength(tour: List<Int>): Double = tourLength(tour.toIntArray())

    companion object {
        private const val EARTH_RADIUS_KM = 6371.0088

        fun haversineKm(a: GeoPoint, b: GeoPoint): Double {
            val lat1 = Math.toRadians(a.latitude)
            val lat2 = Math.toRadians(b.latitude)
            val dLat = lat2 - lat1
            val dLon = Math.toRadians(b.longitude - a.longitude)
            val h = sin(dLat / 2).let { it * it } +
                cos(lat1) * cos(lat2) * sin(dLon / 2).let { it * it }
            return 2 * EARTH_RADIUS_KM * asin(sqrt(h.coerceIn(0.0, 1.0)))
        }
    }
}
