package com.edge.attendance.ui

import android.app.Application
import android.graphics.Bitmap
import android.os.BatteryManager
import android.os.Build
import android.os.SystemClock
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.edge.attendance.data.ApiException
import com.edge.attendance.data.AppPrefs
import com.edge.attendance.data.DeviceKey
import com.edge.attendance.data.Http
import com.edge.attendance.data.MecClient
import com.edge.attendance.data.OpenSessionResponse
import com.edge.attendance.data.PortalClient
import com.edge.attendance.data.ReceiptQueue
import com.edge.attendance.data.ReceiptUploadWorker
import com.edge.attendance.data.RosterEntry
import com.edge.attendance.data.Section
import com.edge.attendance.face.FacePipeline
import com.edge.attendance.face.Matcher
import com.edge.attendance.face.PipelineTimings
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.IOException

enum class Screen { LOGIN, SECTIONS, CAPTURE, REVIEW, DONE }

enum class Status { PRESENT, REVIEW, ABSENT, NOT_ENROLLED }

data class StudentRow(
    val pseudonym: String,
    val rollNo: String,
    val name: String,
    val status: Status,
    val score: Float?,
    val markedPresent: Boolean,
)

data class UiState(
    val screen: Screen = Screen.LOGIN,
    val busy: Boolean = false,
    val message: String? = null,
    val teacherName: String? = null,
    val portalUrl: String = "",
    val mecUrl: String = "",
    val lastUsername: String = "",
    val sections: List<Section> = emptyList(),
    val section: Section? = null,
    val photos: Int = 0,
    val facesSeen: Int = 0,
    val unknownFaces: Int = 0,
    val students: List<StudentRow> = emptyList(),
    val sessionExpiresAt: Long = 0,
    val result: String? = null,
)

/**
 * Orchestrates: portal login -> grant -> MEC session -> on-device matching ->
 * signed submission -> receipt forwarded to the portal.
 *
 * Privacy: photos are processed and dropped immediately; templates live only
 * in the [Matcher] for the length of one session and are wiped after.
 */
class AttendanceViewModel(app: Application) : AndroidViewModel(app) {
    private val prefs = AppPrefs(app)
    private val http = Http.client(app)
    private val deviceKey = DeviceKey()
    private val pipeline = FacePipeline(app)
    private val receipts = ReceiptQueue(app)

    private val _state = MutableStateFlow(
        UiState(portalUrl = prefs.portalUrl, mecUrl = prefs.mecUrl, lastUsername = prefs.lastUsername)
    )
    val state: StateFlow<UiState> = _state.asStateFlow()

    // In memory only. Never persisted.
    private var accessToken: String? = null
    private var username: String = ""
    private var session: OpenSessionResponse? = null
    private var matcher: Matcher? = null
    private var roster: List<RosterEntry> = emptyList()
    private val best = HashMap<String, Float>()   // pseudonym -> best score this session
    private val overrides = HashMap<String, Boolean>()
    private var timings = PipelineTimings()
    private var openRttMs = 0L
    private var batteryAtStart = -1

    private fun portal() = PortalClient(http, prefs.portalUrl)
    private fun mec() = MecClient(http, prefs.mecUrl, deviceKey)

    private fun launchOp(block: suspend () -> Unit) {
        if (_state.value.busy) return
        _state.update { it.copy(busy = true, message = null) }
        viewModelScope.launch {
            try {
                block()
            } catch (e: ApiException) {
                Log.w(TAG, "API error ${e.code}", e)
                _state.update { it.copy(message = friendly(e)) }
            } catch (e: IOException) {
                Log.w(TAG, "Network error", e)
                _state.update { it.copy(message = "Network error: ${e.message ?: "cannot reach server"}. Check Wi-Fi and server addresses.") }
            } catch (e: Exception) {
                Log.e(TAG, "Unexpected error", e)
                _state.update { it.copy(message = "Something went wrong: ${e.message}") }
            } finally {
                _state.update { it.copy(busy = false) }
            }
        }
    }

    private fun friendly(e: ApiException): String = when (e.code) {
        401 -> if (accessToken == null) "Wrong username or password." else "Not authorised: ${e.message}"
        409 -> "Already used: ${e.message}. Start a new session."
        410 -> "The session expired. Start again."
        else -> "Server said: ${e.message}"
    }

    fun dismissMessage() = _state.update { it.copy(message = null) }
    fun showMessage(message: String) = _state.update { it.copy(message = message) }

    // ---- login -------------------------------------------------------------
    fun login(user: String, password: String, portalUrl: String, mecUrl: String) = launchOp {
        prefs.portalUrl = portalUrl
        prefs.mecUrl = mecUrl
        val resp = portal().login(user.trim(), password)
        accessToken = resp.access_token
        username = user.trim()
        prefs.lastUsername = username
        ensureDeviceRegistered(resp.access_token)
        val sections = portal().sections(resp.access_token)
        _state.update {
            it.copy(screen = Screen.SECTIONS, teacherName = resp.name, sections = sections,
                portalUrl = prefs.portalUrl, mecUrl = prefs.mecUrl, lastUsername = username)
        }
        ReceiptUploadWorker.schedule(getApplication()) // flush anything left from last time
    }

    private suspend fun ensureDeviceRegistered(token: String) {
        if (prefs.deviceId(username, prefs.mecUrl) != null) return
        val id = mec().registerDevice(token, "${Build.MANUFACTURER} ${Build.MODEL}")
        prefs.setDeviceId(username, prefs.mecUrl, id)
    }

    fun logout() {
        endSession()
        accessToken = null
        _state.update { UiState(portalUrl = prefs.portalUrl, mecUrl = prefs.mecUrl, lastUsername = prefs.lastUsername) }
    }

    fun refreshSections() = launchOp {
        val token = accessToken ?: return@launchOp
        _state.update { it.copy(sections = portal().sections(token)) }
    }

    // ---- session -----------------------------------------------------------
    fun startSession(section: Section) = launchOp {
        val token = accessToken ?: return@launchOp
        val grant = portal().grant(token, section.id)
        val deviceId = prefs.deviceId(username, prefs.mecUrl) ?: error("device not registered")
        val t0 = SystemClock.elapsedRealtime()
        val opened = try {
            mec().openSession(grant.grant_token, deviceId)
        } catch (e: ApiException) {
            if (e.code == 401 && e.message?.contains("device") == true) {
                prefs.setDeviceId(username, prefs.mecUrl, null) // revoked or MEC reset: re-register next login
            }
            throw e
        }
        openRttMs = SystemClock.elapsedRealtime() - t0

        session = opened
        roster = grant.roster
        matcher = Matcher(
            templates = opened.templates.map { it.pseudonym to Matcher.decodeVector(it.vector) },
            permutation = opened.transform.permutation.toIntArray(),
            signs = FloatArray(opened.transform.signs.size) { opened.transform.signs[it].toFloat() },
        )
        best.clear(); overrides.clear()
        timings = PipelineTimings()
        batteryAtStart = batteryPercent()
        _state.update {
            it.copy(screen = Screen.CAPTURE, section = section, photos = 0, facesSeen = 0, unknownFaces = 0,
                students = rows(), sessionExpiresAt = opened.expires_at, result = null)
        }
    }

    /** Called with each captured photo. The bitmap is always wiped and recycled here. */
    fun onPhoto(photo: Bitmap) {
        val m = matcher
        if (m == null || _state.value.busy) {
            photo.eraseColor(0)
            photo.recycle()
            return
        }
        launchOp { processPhoto(m, photo) }
    }

    private suspend fun processPhoto(m: Matcher, photo: Bitmap) {
        try {
            val vectors = pipeline.embeddings(photo, timings)
            val t0 = SystemClock.elapsedRealtime()
            val result = m.matchPhoto(vectors)
            timings.matchMs += SystemClock.elapsedRealtime() - t0
            vectors.forEach { it.fill(0f) }
            for (match in result.matches) {
                if (match.score > (best[match.pseudonym] ?: -1f)) best[match.pseudonym] = match.score
            }
            _state.update {
                it.copy(photos = timings.photos, facesSeen = timings.faces,
                    unknownFaces = it.unknownFaces + result.unmatchedFaces, students = rows())
            }
        } finally {
            photo.eraseColor(0)
            photo.recycle()
        }
    }

    fun toReview() = _state.update { it.copy(screen = Screen.REVIEW, students = rows()) }
    fun backToCapture() = _state.update { it.copy(screen = Screen.CAPTURE) }

    fun setPresent(pseudonym: String, present: Boolean) {
        overrides[pseudonym] = present
        _state.update { it.copy(students = rows()) }
    }

    private fun rows(): List<StudentRow> {
        val enrolled = session?.templates?.map { it.pseudonym }?.toSet() ?: emptySet()
        return roster.map { r ->
            val score = best[r.pseudonym]
            val status = when {
                r.pseudonym !in enrolled -> Status.NOT_ENROLLED
                score == null -> Status.ABSENT
                score >= Matcher.ACCEPT -> Status.PRESENT
                else -> Status.REVIEW
            }
            StudentRow(r.pseudonym, r.roll_no, r.name, status, score,
                markedPresent = overrides[r.pseudonym] ?: (status == Status.PRESENT))
        }.sortedWith(compareBy({ it.status.ordinal }, { it.rollNo }))
    }

    fun submit() = launchOp {
        val s = session ?: return@launchOp
        val deviceId = prefs.deviceId(username, prefs.mecUrl) ?: error("device not registered")
        val present = rows().filter { it.markedPresent }.map { it.pseudonym }
        val resp = mec().submit(deviceId, s.session_id, s.nonce, present, metrics())
        val forwarded = try {
            val r = portal().postReceipt(resp.receipt)
            "Recorded on the portal: ${r.present} present, ${r.absent} absent."
        } catch (e: IOException) {
            receipts.add(resp.receipt)
            ReceiptUploadWorker.schedule(getApplication())
            "Verified by the MEC (${present.size} present). The portal is unreachable, so the result is queued and will upload automatically."
        }
        endSession()
        _state.update { it.copy(screen = Screen.DONE, result = forwarded) }
    }

    private fun metrics(): JsonObject = buildJsonObject {
        put("photos", timings.photos)
        put("faces", timings.faces)
        put("templates", matcher?.size ?: 0)
        put("detect_ms", timings.detectMs)
        put("embed_ms", timings.embedMs)
        put("match_ms", timings.matchMs)
        put("open_session_rtt_ms", openRttMs)
        put("battery_start", batteryAtStart)
        put("battery_end", batteryPercent())
        put("device", "${Build.MANUFACTURER} ${Build.MODEL}")
        put("sdk", Build.VERSION.SDK_INT)
    }

    private fun batteryPercent(): Int =
        (getApplication<Application>().getSystemService(BatteryManager::class.java))
            ?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY) ?: -1

    fun cancelSession() {
        endSession()
        _state.update { it.copy(screen = Screen.SECTIONS, students = emptyList()) }
    }

    fun backToSections() = _state.update { it.copy(screen = Screen.SECTIONS, result = null) }

    /** Wipe every trace of the session from memory. */
    private fun endSession() {
        matcher?.wipe()
        matcher = null
        session = null
        roster = emptyList()
        best.clear()
        overrides.clear()
    }

    override fun onCleared() {
        endSession()
        pipeline.close()
    }

    private companion object { const val TAG = "Attendance" }
}
