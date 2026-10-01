package com.kavi.app.denoise

class GtcrnDenoise {
    external fun nativeDenoise(audio: ByteArray): FloatArray
    init { System.loadLibrary("qnn_loader_jni") }
}
