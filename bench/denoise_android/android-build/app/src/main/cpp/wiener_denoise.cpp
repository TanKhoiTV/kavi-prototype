// Wiener filter — portable noisereduce logic (stub)
#include <jni.h>
#include <android/log.h>

extern "C" JNIEXPORT jfloatArray JNICALL
Java_com_kavi_app_denoise_WienerDenoise_nativeDenoise(JNIEnv*, jobject, jbyteArray audio) {
    __android_log_print(ANDROID_LOG_INFO, "WIENER", "Wiener denoise (prop_decrease=0.5)");
    return nullptr;
}
