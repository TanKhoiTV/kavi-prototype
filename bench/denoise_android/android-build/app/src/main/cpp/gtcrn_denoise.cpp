// GTCRN integration — sherpa-onnx OfflineDenoise JNI stub
#include <jni.h>
#include <android/log.h>

extern "C" JNIEXPORT jfloatArray JNICALL
Java_com_kavi_app_denoise_GtcrnDenoise_nativeDenoise(JNIEnv*, jobject, jbyteArray audio) {
    __android_log_print(ANDROID_LOG_INFO, "GTCRN", "GTCRN denoise invoked");
    return nullptr; // real: call sherpa-onnx, return denoised audio
}
