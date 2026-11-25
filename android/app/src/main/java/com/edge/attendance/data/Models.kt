@file:Suppress("PropertyName") // field names mirror the server's JSON exactly

package com.edge.attendance.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

// ---- Portal ---------------------------------------------------------------
@Serializable data class LoginRequest(val username: String, val password: String)
@Serializable data class LoginResponse(val access_token: String, val expires_in: Int, val name: String)
@Serializable data class Section(val id: String, val title: String, val student_count: Int)
@Serializable data class RosterEntry(val pseudonym: String, val roll_no: String, val name: String)
@Serializable data class GrantResponse(
    val grant_token: String,
    val expires_in: Int,
    val section_id: String,
    val roster: List<RosterEntry>,
)
@Serializable data class ReceiptRequest(val receipt: String)
@Serializable data class ReceiptResponse(val session_id: String, val recorded: Boolean, val present: Int, val absent: Int)

// ---- MEC (bodies are signed byte-for-byte as serialised) --------------------
@Serializable data class RegisterDeviceBody(val public_key_pem: String, val label: String, val timestamp: Long)
@Serializable data class RegisterDeviceResponse(val device_id: String)
@Serializable data class OpenSessionBody(val device_id: String, val timestamp: Long)
@Serializable data class TransformWire(val version: Int, val permutation: List<Int>, val signs: List<Int>)
@Serializable data class TemplateWire(val pseudonym: String, val vector: String)
@Serializable data class Thresholds(val accept: Float, val review: Float)
@Serializable data class OpenSessionResponse(
    val session_id: String,
    val nonce: String,
    val expires_at: Long,
    val embedding_dim: Int,
    val transform: TransformWire,
    val templates: List<TemplateWire>,
    val not_enrolled: List<String>,
    val thresholds: Thresholds? = null, // set on the portal's Settings page
)
@Serializable data class SubmitBody(
    val device_id: String,
    val session_id: String,
    val nonce: String,
    val timestamp: Long,
    val present: List<String>,
    val metrics: JsonObject? = null,
    val evidence: Evidence? = null,
)
@Serializable data class EvidenceFace(val box: List<Int>, val pseudonym: String?, val score: Float?)
@Serializable data class Evidence(val jpeg_b64: String, val width: Int, val height: Int, val faces: List<EvidenceFace>)
@Serializable data class SubmitResponse(val session_id: String, val recorded: Int, val receipt: String)
