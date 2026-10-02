package com.example.seoultsp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.seoultsp.sim.SimulationController

/** 화면 회전 등 구성 변경에도 시뮬레이션 상태가 유지되도록 컨트롤러를 보관합니다. */
class SimulationViewModel : ViewModel() {
    val controller = SimulationController(viewModelScope)
}
