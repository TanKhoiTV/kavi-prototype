package com.kavi.app.denoise

class WienerDenoise {
    external fun nativeDenoise(audio: ByteArray): FloatArray
    init { System.loadLibrary("qnn_loader_jni") }
}
