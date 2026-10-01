package com.kavi.app.runner

import android.content.Context
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader

/**
 * Single item from the eval manifest.
 *
 * Field names match `bench/schema.py:EvalItem` for consistency.
 */
data class EvalItem(
    val id: String,
    val stage: String, // "ASR" | "MT" | "TTS"
    val language: String, // "vi" | "en"
    val direction: String,
    val candidateId: String?,
    val modelPath: String?,
    val config: Map<String, Any>,
    val audioRef: String?,
    val transcriptRef: String?,
    val inputText: String?,
    val referenceText: String?,
    val snr: Double?,
    val noiseType: String?,
)

/**
 * Reads `eval_manifest_v1.json` from app assets and deserialises it
 * into a list of [EvalItem].
 *
 * Usage:
 * ```kotlin
 * val reader = ManifestReader(context)
 * val allItems = reader.readManifest()
 * val asrItems = reader.readManifest(filterStage = "ASR")
 * val viItems = reader.readManifest(filterStage = "ASR", filterLanguage = "vi")
 * ```
 */
class ManifestReader(
    private val appContext: Context,
) {
    companion object {
        private const val TAG = "ManifestReader"
        private const val MANIFEST_FILE = "eval_manifest_v1.json"
    }

    /**
     * Read and optionally filter the eval manifest.
     *
     * @param assetPath     Override asset path (default: `eval_manifest_v1.json`).
     * @param filterStage   If non-null, only return items matching this stage.
     * @param filterLanguage If non-null, only return items matching this language.
     * @return Parsed list of [EvalItem].
     */
    fun readManifest(
        assetPath: String = MANIFEST_FILE,
        filterStage: String? = null,
        filterLanguage: String? = null,
    ): List<EvalItem> {
        val jsonText = readAssetText(assetPath)
        val root = JSONObject(jsonText)
        val version = root.optString("version", "unknown")
        val rawItems = root.getJSONArray("items")

        val items = mutableListOf<EvalItem>()
        for (i in 0 until rawItems.length()) {
            val obj = rawItems.getJSONObject(i)

            val item = parseEvalItem(obj)
            if (filterStage != null && item.stage != filterStage) continue
            if (filterLanguage != null && item.language != filterLanguage) continue

            items.add(item)
        }

        Log.i(
            TAG,
            "Read $MANIFEST_FILE v$version: ${items.size}/${rawItems.length()} items" +
                (if (filterStage != null) " [stage=$filterStage]" else "") +
                (if (filterLanguage != null) " [lang=$filterLanguage]" else ""),
        )

        return items
    }

    // ---------- internal ----------

    private fun parseEvalItem(obj: JSONObject): EvalItem =
        EvalItem(
            id = obj.getString("id"),
            stage = obj.getString("stage"),
            language = obj.getString("language"),
            direction = obj.optString("direction", ""),
            candidateId = obj.optString("candidate_id", null),
            modelPath = obj.optString("model_path", null),
            config = parseConfig(obj.optJSONObject("config")),
            audioRef = obj.optString("audio_ref", null),
            transcriptRef = obj.optString("transcript_ref", null),
            inputText = obj.optString("input_text", null),
            referenceText = obj.optString("reference_text", null),
            snr = if (obj.has("snr") && !obj.isNull("snr")) obj.getDouble("snr") else null,
            noiseType = obj.optString("noise_type", null),
        )

    @Suppress("UNCHECKED_CAST")
    private fun parseConfig(configObj: JSONObject?): Map<String, Any> {
        if (configObj == null) return emptyMap()
        val map = mutableMapOf<String, Any>()
        for (key in configObj.keys()) {
            val value = configObj.get(key)
            when (value) {
                is Int, is Long, is Double, is Boolean, is String -> {
                    map[key] = value as Any
                }

                is JSONObject, is JSONArray -> {
                    map[key] = value.toString()
                }

                else -> {
                    map[key] = value?.toString() ?: ""
                }
            }
        }
        return map
    }

    private fun readAssetText(assetPath: String): String =
        appContext.assets.open(assetPath).use { inputStream ->
            BufferedReader(InputStreamReader(inputStream, Charsets.UTF_8)).use { reader ->
                reader.readText()
            }
        }
}
