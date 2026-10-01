## Mục tiêu
Hoàn thiện pipeline 3 option denoiser (VAD-only / GTCRN / Wiener) theo **ADR-018** để giải quyết **#111** (chọn model denoiser on-device).

## Thay đổi
- `bench/denoise_android/android-build/app/src/main/cpp/gtcrn_denoise.cpp`
- `wiener_denoise.cpp`
- `CMakeLists.txt` (thêm cả 2 native)
- `java/com/kavi/app/denoise/DenoisingPipeline.kt`
- `GtcrnDenoise.kt` / `WienerDenoise.kt`
- `MainActivity.kt` (kết nối pipeline + đo → `/sdcard/denoising_results.json`)
- `local.properties`

## Hướng dẫn kết nối ADB và chạy đo
```bash
# 1. Cắm USB Meizu 21 Note; bật USB Debugging; cho phép kết nối
adb devices

# 2. Build APK (cần Java 17 + Android SDK)
export JAVA_HOME=/tmp/jdk-17.0.12+7/Contents/Home
export ANDROID_HOME=$HOME/Library/Android/sdk
./gradlew :app:assembleRelease

# 3. Cài APK + đẩy manifest/test
adb install app/build/outputs/apk/release/app-release.apk
adb push eval_manifest_v1.json /sdcard/

# 4. Chạy pipeline trên thiết bị
adb shell am start -n com.kavi.app/.MainActivity

# 5. Pull kết quả đo WER/RTF
adb pull /sdcard/denoising_results.json
```

## Kết quả mong đợi (ADR-018)
- Đo GTCRN và Wiener trên Meizu 21 Note (SD8G2)
- Ghi WER/RTF vào ADR-018
- Chọn model, đóng parameter #2

## Liên quan
- Closes #111
- ADR-018 (tiered denoising slot, model pick OPEN → closed)
