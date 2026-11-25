package com.edge.attendance.data

import android.content.Context
import com.edge.attendance.BuildConfig

/** Non-sensitive settings only: server URLs, last username, device ids. No tokens, no face data. */
class AppPrefs(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("attendance", Context.MODE_PRIVATE)

    var portalUrl: String
        get() = prefs.getString("portal_url", DEFAULT_PORTAL)!!
        set(v) = prefs.edit().putString("portal_url", v.trim()).apply()

    var mecUrl: String
        get() = prefs.getString("mec_url", DEFAULT_MEC)!!
        set(v) = prefs.edit().putString("mec_url", v.trim()).apply()

    /** Start of the server certificate's SHA-256, printed by start.ps1. Empty = only the built-in certificate. */
    var serverCode: String
        get() = prefs.getString("server_code", "")!!
        set(v) = prefs.edit().putString("server_code", v.trim()).apply()

    var lastUsername: String
        get() = prefs.getString("last_username", "")!!
        set(v) = prefs.edit().putString("last_username", v).apply()

    /** The MEC registers a device per teacher, so remember one id per (teacher, MEC). */
    fun deviceId(username: String, mecUrl: String): String? = prefs.getString(deviceKey(username, mecUrl), null)

    fun setDeviceId(username: String, mecUrl: String, id: String?) =
        prefs.edit().apply { if (id == null) remove(deviceKey(username, mecUrl)) else putString(deviceKey(username, mecUrl), id) }.apply()

    private fun deviceKey(username: String, mecUrl: String) = "device_id|$username|${mecUrl.trimEnd('/')}"

    companion object {
        // The laptop's address at build time; change it in the app's server settings.
        const val DEFAULT_PORTAL = "https://${BuildConfig.SERVER_IP}:8001"
        const val DEFAULT_MEC = "https://${BuildConfig.SERVER_IP}:8000"
    }
}
