package com.example.seoultsp.ga

/** 위도·경도 좌표 (도 단위). */
data class GeoPoint(val latitude: Double, val longitude: Double)

/** 순회 대상이 되는 관광지 하나. [id]는 [SeoulAttractions.all] 안에서의 인덱스와 같습니다. */
data class Attraction(
    val id: Int,
    val name: String,
    val englishName: String,
    val location: GeoPoint,
)
