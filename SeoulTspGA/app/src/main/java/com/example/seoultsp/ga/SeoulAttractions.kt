package com.example.seoultsp.ga

/** 시뮬레이션에 사용하는 서울의 대표 관광지 20곳과 지도 표시용 보조 데이터. */
object SeoulAttractions {

    val all: List<Attraction> = listOf(
        Attraction(0, "경복궁", "Gyeongbokgung Palace", GeoPoint(37.5796, 126.9770)),
        Attraction(1, "창덕궁", "Changdeokgung Palace", GeoPoint(37.5794, 126.9910)),
        Attraction(2, "덕수궁", "Deoksugung Palace", GeoPoint(37.5658, 126.9751)),
        Attraction(3, "북촌한옥마을", "Bukchon Hanok Village", GeoPoint(37.5826, 126.9831)),
        Attraction(4, "인사동", "Insadong", GeoPoint(37.5717, 126.9856)),
        Attraction(5, "명동", "Myeongdong", GeoPoint(37.5636, 126.9850)),
        Attraction(6, "N서울타워", "N Seoul Tower", GeoPoint(37.5512, 126.9882)),
        Attraction(7, "동대문디자인플라자", "Dongdaemun Design Plaza", GeoPoint(37.5667, 127.0090)),
        Attraction(8, "광장시장", "Gwangjang Market", GeoPoint(37.5701, 126.9997)),
        Attraction(9, "남대문시장", "Namdaemun Market", GeoPoint(37.5591, 126.9776)),
        Attraction(10, "이태원", "Itaewon", GeoPoint(37.5347, 126.9947)),
        Attraction(11, "국립중앙박물관", "National Museum of Korea", GeoPoint(37.5239, 126.9803)),
        Attraction(12, "홍대거리", "Hongdae Street", GeoPoint(37.5563, 126.9236)),
        Attraction(13, "여의도한강공원", "Yeouido Hangang Park", GeoPoint(37.5284, 126.9326)),
        Attraction(14, "하늘공원", "Haneul Park", GeoPoint(37.5683, 126.8851)),
        Attraction(15, "서울숲", "Seoul Forest", GeoPoint(37.5443, 127.0374)),
        Attraction(16, "가로수길", "Garosu-gil", GeoPoint(37.5205, 127.0230)),
        Attraction(17, "코엑스", "COEX", GeoPoint(37.5116, 127.0594)),
        Attraction(18, "롯데월드타워", "Lotte World Tower", GeoPoint(37.5126, 127.1025)),
        Attraction(19, "올림픽공원", "Olympic Park", GeoPoint(37.5206, 127.1214)),
    )

    /** 지도 배경에 그리는 한강 중심선의 개략적인 좌표 (서쪽 → 동쪽). 계산에는 쓰이지 않습니다. */
    val hanRiver: List<GeoPoint> = listOf(
        GeoPoint(37.585, 126.835),
        GeoPoint(37.570, 126.862),
        GeoPoint(37.560, 126.880),
        GeoPoint(37.547, 126.900),
        GeoPoint(37.538, 126.922),
        GeoPoint(37.533, 126.935),
        GeoPoint(37.526, 126.948),
        GeoPoint(37.518, 126.962),
        GeoPoint(37.513, 126.980),
        GeoPoint(37.513, 126.996),
        GeoPoint(37.524, 127.011),
        GeoPoint(37.535, 127.022),
        GeoPoint(37.537, 127.037),
        GeoPoint(37.532, 127.055),
        GeoPoint(37.524, 127.070),
        GeoPoint(37.521, 127.085),
        GeoPoint(37.528, 127.100),
        GeoPoint(37.543, 127.115),
        GeoPoint(37.556, 127.130),
        GeoPoint(37.570, 127.150),
    )

    /**
     * Held-Karp 동적 계획법으로 미리 계산한 정답 경로 (직선거리 기준).
     * 시뮬레이션 결과가 최적해에 얼마나 가까운지 비교하는 기준선으로 사용합니다.
     */
    val optimalTour: List<Int> = listOf(0, 4, 5, 6, 9, 2, 12, 14, 13, 11, 10, 16, 17, 18, 19, 15, 7, 8, 1, 3)

    /** [optimalTour]의 총 이동 거리 (km). */
    const val OPTIMAL_TOUR_KM: Double = 52.92414550728623
}
