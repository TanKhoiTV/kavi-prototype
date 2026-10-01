package com.kavi.app.denoise

object DenoisingPipeline {
    const val OPTION_RAW = 0   // VAD-only / raw (ADR-018 Tier 3 skip)
    const val OPTION_GTCRN = 1 // sherpa-onnx OfflineDenoise
    const val OPTION_WIENER = 2 // noisereduce port

    fun select(option: Int): String = when(option) {
        OPTION_GTCRN -> GtcrnDenoise().nativeDenoise(ByteArray(0)).toString()
        OPTION_WIENER -> WienerDenoise().nativeDenoise(ByteArray(0)).toString()
        else -> "raw"
    }
}
