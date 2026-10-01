package com.kavi.app.runner

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.util.Log

/**
 * Checks device connectivity state to ensure benchmark runs are offline.
 *
 * Kavi is designed as a fully offline app. This monitor enforces that
 * no network access occurs during benchmark execution.
 *
 * Usage:
 * ```kotlin
 * val monitor = NetworkMonitor(context)
 * if (!monitor.isOffline()) {
 *     Log.w("NetworkMonitor", "Turn on flight mode before benchmarking")
 *     return
 * }
 * ```
 */
class NetworkMonitor(
    private val appContext: Context,
) {
    companion object {
        private const val TAG = "NetworkMonitor"
    }

    /** Returns `true` if the device has zero active network connections. */
    fun isOffline(): Boolean {
        val connectivityManager =
            appContext.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
                ?: return true // no connectivity service -> assume offline

        val network = connectivityManager.activeNetwork ?: return true
        val caps = connectivityManager.getNetworkCapabilities(network) ?: return true

        val hasInternet =
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
                caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)

        return !hasInternet
    }

    /**
     * Log the current connectivity state.
     *
     * @return `true` if offline (safe to benchmark).
     */
    fun assertOffline(): Boolean {
        val offline = isOffline()
        if (offline) {
            Log.i(TAG, "Device is OFFLINE — safe to benchmark")
        } else {
            val detail = describeConnectivity()
            Log.w(TAG, "Device has network access — enable flight mode: $detail")
        }
        return offline
    }

    /** Human-readable connectivity detail string. */
    fun describeConnectivity(): String {
        val cm =
            appContext.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
                ?: return "no connectivity service"

        val network = cm.activeNetwork
        if (network == null) return "no active network"

        val caps = cm.getNetworkCapabilities(network) ?: return "no capabilities"

        val parts = mutableListOf<String>()
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) parts.add("WiFi")
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) parts.add("Cellular")
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) parts.add("Ethernet")
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_BLUETOOTH)) parts.add("Bluetooth")

        return if (parts.isEmpty()) "unknown transport" else parts.joinToString("+")
    }
}
