# HelloAndroid

화면 가운데에 **hello ANDROID** 를 출력하는 가장 간단한 안드로이드 앱입니다. (Kotlin + Jetpack Compose)

## 실행 방법 (Android Studio)

1. 이 저장소를 내 컴퓨터로 받습니다 (`git clone` 또는 GitHub에서 ZIP 다운로드 후 압축 해제).
2. Android Studio 실행 → **File > Open** → `HelloAndroid` 폴더 선택.
3. Gradle Sync가 끝날 때까지 기다립니다 (처음엔 필요한 파일을 내려받느라 몇 분 걸릴 수 있습니다).
4. 상단 기기 목록에서 에뮬레이터(또는 USB로 연결한 휴대폰)를 고르고 ▶ **Run 'app'** 클릭.

> 에뮬레이터가 없다면 **Tools > Device Manager** 에서 가상 기기를 하나 만드세요.

## 핵심 코드

`app/src/main/java/com/example/helloandroid/MainActivity.kt`

```kotlin
Text(text = "hello ANDROID", fontSize = 32.sp)
```

## 요구 사항

- Android Studio Ladybug (2024.2) 이상
- Android Gradle Plugin 8.7.3 / Gradle 8.11.1 / Kotlin 2.0.21
- minSdk 24 (Android 7.0), targetSdk 35
