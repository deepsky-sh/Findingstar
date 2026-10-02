package com.example.seoultsp

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import com.example.seoultsp.ui.SeoulTspApp
import com.example.seoultsp.ui.theme.SeoulTspTheme

class MainActivity : ComponentActivity() {

    private val viewModel: SimulationViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            SeoulTspTheme {
                SeoulTspApp(viewModel.controller)
            }
        }
    }

    override fun onStop() {
        super.onStop()
        // 앱이 화면에서 사라지면 계산을 멈춥니다. 화면 회전 때는 그대로 이어서 실행합니다.
        if (!isChangingConfigurations) viewModel.controller.pause()
    }
}
