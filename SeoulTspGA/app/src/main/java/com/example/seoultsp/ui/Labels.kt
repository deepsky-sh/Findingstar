package com.example.seoultsp.ui

import com.example.seoultsp.ga.CrossoverMethod
import com.example.seoultsp.ga.MutationMethod
import com.example.seoultsp.ga.SelectionMethod
import com.example.seoultsp.sim.SimSpeed
import com.example.seoultsp.sim.SimStatus

val SelectionMethod.label: String
    get() = when (this) {
        SelectionMethod.Tournament -> "토너먼트"
        SelectionMethod.Roulette -> "룰렛휠"
        SelectionMethod.Rank -> "순위"
    }

val SelectionMethod.description: String
    get() = when (this) {
        SelectionMethod.Tournament -> "무작위로 k개 개체를 뽑아 그중 가장 짧은 경로를 부모로 고릅니다. k가 클수록 선택압이 강해집니다."
        SelectionMethod.Roulette -> "(최악 거리 − 내 거리)에 비례하는 넓이의 칸을 가진 룰렛을 돌려 부모를 고릅니다."
        SelectionMethod.Rank -> "거리 순위에 비례한 확률로 고릅니다. 값의 크기 차이에 덜 민감해 조기 수렴을 줄여 줍니다."
    }

val CrossoverMethod.label: String
    get() = when (this) {
        CrossoverMethod.OX -> "OX 순서"
        CrossoverMethod.PMX -> "PMX 매핑"
        CrossoverMethod.CX -> "CX 사이클"
    }

val CrossoverMethod.description: String
    get() = when (this) {
        CrossoverMethod.OX -> "부모1의 한 구간을 그대로 물려받고, 나머지 자리는 부모2에 나오는 순서대로 채웁니다."
        CrossoverMethod.PMX -> "부모1의 구간을 복사한 뒤, 부모2 구간과의 매핑 관계를 따라가며 중복 없이 나머지를 채웁니다."
        CrossoverMethod.CX -> "두 부모 사이의 위치 사이클을 찾아 사이클마다 번갈아 한쪽 부모의 값을 그 자리 그대로 물려받습니다."
    }

val MutationMethod.label: String
    get() = when (this) {
        MutationMethod.Swap -> "교환"
        MutationMethod.Inversion -> "역위"
        MutationMethod.Scramble -> "뒤섞기"
        MutationMethod.Insertion -> "삽입"
    }

val MutationMethod.description: String
    get() = when (this) {
        MutationMethod.Swap -> "임의의 두 관광지의 방문 순서를 맞바꿉니다."
        MutationMethod.Inversion -> "임의 구간의 방문 순서를 거꾸로 뒤집습니다. 교차된 경로를 푸는 2-opt와 같은 효과가 있습니다."
        MutationMethod.Scramble -> "임의 구간 안의 방문 순서를 무작위로 섞습니다."
        MutationMethod.Insertion -> "관광지 하나를 꺼내 다른 위치에 끼워 넣습니다."
    }

val SimSpeed.label: String
    get() = when (this) {
        SimSpeed.Slow -> "느리게"
        SimSpeed.Normal -> "보통"
        SimSpeed.Fast -> "빠르게"
        SimSpeed.Max -> "최고속"
    }

val SimStatus.label: String
    get() = when (this) {
        SimStatus.Ready -> "준비"
        SimStatus.Running -> "진화 중"
        SimStatus.Paused -> "일시정지"
        SimStatus.Finished -> "완료"
    }
