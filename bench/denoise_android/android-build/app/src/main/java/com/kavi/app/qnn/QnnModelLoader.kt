package com.kavi.app.qnn

import android.content.Context
import android.util.Log
import java.io.File
import java.io.FileOutputStream

/**
 * Result of a single QNN inference run.
 *
 * @property outputTensor  Raw bytes of the output tensor (FP32 or quantized).
 * @property latencyMs     Wall-clock inference time in milliseconds.
 * @property peakRssKb     Peak resident set size in kilobytes (approximate).
 */
data class QnnInferenceResult(
    val outputTensor: ByteArray,
    val latencyMs: Long,
    val peakRssKb: Long,
)

/**
 * High-level loader for QNN HTP v73 context binaries on Android.
 *
 * Usage:
 * ```kotlin
 * val loader = QnnModelLoader(context)
 * loader.initialize()
 * val result = loader.runInference(inputBytes, "input_features", "last_hidden_state")
 * Log.d("QNN", "Latency: ${result.latencyMs}ms, RSS: ${result.peakRssKb}KB")
 * loader.shutdown()
 * ```
 */
class QnnModelLoader(
    private val appContext: Context,
) {
    companion object {
        private const val TAG = "QnnModelLoader"
        private const val QNN_BACKEND_LIB = "QnnHtp"
        private const val JNI_BRIDGE_LIB = "qnn_loader_jni"

        init {
            try {
                System.loadLibrary(JNI_BRIDGE_LIB)
            } catch (e: UnsatisfiedLinkError) {
                Log.w(TAG, "JNI bridge library not pre-loaded: ${e.message}")
            }
        }
    }

    // ---------- internal state ----------

    /** Whether the backend has been initialized. */
    private var initialized: Boolean = false

    /** Path to the extracted context binary on the filesystem. */
    private var contextBinaryPath: String? = null

    /** Handle returned by the native init. */
    private var nativeHandle: Long = 0L

    // ---------- public API ----------

    /**
     * Initialise the QNN HTP backend.
     *
     * Loads [libQnnHtp.so] via `System.loadLibrary` and prepares the runtime.
     * Call once before [runInference].
     */
    fun initialize() {
        if (initialized) return
        try {
            // Ensure JNI bridge library is loaded (companion init may have failed)
            try {
                System.loadLibrary(JNI_BRIDGE_LIB)
            } catch (_: UnsatisfiedLinkError) {
                // Already loaded or not yet built
            }
            System.loadLibrary(QNN_BACKEND_LIB)
            nativeHandle = nativeInit()
            if (nativeHandle == 0L) {
                throw IllegalStateException("nativeInit returned null handle")
            }
            initialized = true
            Log.i(TAG, "QNN HTP backend initialized (handle=$nativeHandle)")
        } catch (e: UnsatisfiedLinkError) {
            Log.e(TAG, "Failed to load $QNN_BACKEND_LIB", e)
            throw IllegalStateException(
                "QNN HTP library not found — ensure libQnnHtp.so is in jniLibs/arm64-v8a/",
                e,
            )
        }
    }

    /**
     * Load a context binary from assets and register it with the backend.
     *
     * @param assetPath  Path inside `src/main/assets/`, e.g. `"whisper_small_encoder_v73.bin"`.
     */
    fun loadContextBinary(assetPath: String) {
        check(initialized) { "call initialize() first" }
        val extracted = extractAssetToCache(assetPath)
        contextBinaryPath = extracted.absolutePath
        val loaded = nativeLoadContext(nativeHandle, extracted.absolutePath)
        if (!loaded) {
            throw IllegalStateException("nativeLoadContext failed for $assetPath")
        }
        Log.i(TAG, "Context binary loaded: $assetPath (${extracted.length()} bytes)")
    }

    /**
     * Run synchronous inference on the loaded context binary.
     *
     * @param inputTensor   Raw float32 (or quantized) input bytes.
     * @param inputName     Name of the input tensor in the QNN graph.
     * @param outputName    Name of the output tensor in the QNN graph.
     * @return [QnnInferenceResult] with output + timing.
     */
    fun runInference(
        inputTensor: ByteArray,
        inputName: String,
        outputName: String,
    ): QnnInferenceResult {
        check(initialized) { "call initialize() first" }
        check(contextBinaryPath != null) { "call loadContextBinary() first" }

        val startRss = readPeakRssKb()
        val startNs = System.nanoTime()

        val outputBytes =
            nativeExecute(
                nativeHandle,
                inputTensor,
                inputName,
                outputName,
            )

        val endNs = System.nanoTime()
        val endRss = readPeakRssKb()

        val latencyMs = (endNs - startNs) / 1_000_000L
        val peakRss = maxOf(startRss, endRss)

        Log.i(TAG, "Inference done: ${latencyMs}ms, ${outputBytes.size} bytes out, RSS ~${peakRss}KB")

        return QnnInferenceResult(
            outputTensor = outputBytes,
            latencyMs = latencyMs,
            peakRssKb = peakRss,
        )
    }

    /** Tear down the backend and release native resources. */
    fun shutdown() {
        if (!initialized) return
        try {
            nativeShutdown(nativeHandle)
        } catch (e: Exception) {
            Log.w(TAG, "nativeShutdown threw", e)
        }
        initialized = false
        nativeHandle = 0L
        contextBinaryPath = null
        Log.i(TAG, "QNN backend shut down")
    }

    // ---------- internal helpers ----------

    /**
     * Copy an asset file to the app's cache directory so the native code
     * can access it via a plain file path.
     */
    private fun extractAssetToCache(assetPath: String): File {
        val fileName = assetPath.substringAfterLast('/')
        val cacheFile = File(appContext.cacheDir, fileName)

        if (cacheFile.exists() && cacheFile.length() > 0L) {
            return cacheFile // already extracted
        }

        appContext.assets.open(assetPath).use { input ->
            FileOutputStream(cacheFile).use { output ->
                input.copyTo(output)
            }
        }
        Log.d(TAG, "Extracted $assetPath -> ${cacheFile.absolutePath} (${cacheFile.length()} bytes)")
        return cacheFile
    }

    /** Read /proc/self/status VmPeak as a rough RSS estimate (KB). */
    private fun readPeakRssKb(): Long {
        return try {
            val status = File("/proc/self/status").readText()
            val line = status.lines().firstOrNull { it.startsWith("VmPeak:") } ?: return 0L
            val kb = line.replace(Regex("[^0-9]"), "")
            kb.toLongOrNull() ?: 0L
        } catch (_: Exception) {
            0L
        }
    }

    // ---------- JNI declarations ----------

    private external fun nativeInit(): Long

    private external fun nativeLoadContext(
        handle: Long,
        binaryPath: String,
    ): Boolean

    private external fun nativeExecute(
        handle: Long,
        inputTensor: ByteArray,
        inputName: String,
        outputName: String,
    ): ByteArray

    private external fun nativeShutdown(handle: Long)
}
