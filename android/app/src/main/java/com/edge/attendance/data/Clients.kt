package com.edge.attendance.data

import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

private val JSON_TYPE = "application/json".toMediaType()

private fun HttpUrl.withPath(vararg segments: String): HttpUrl =
    newBuilder().apply { segments.forEach { addPathSegment(it) } }.build()

private fun now(): Long = System.currentTimeMillis() / 1000

/** Online attendance portal: login, sections, grants, receipts. */
class PortalClient(private val http: OkHttpClient, baseUrl: String) {
    private val base = baseUrl.trim().trimEnd('/').toHttpUrl()

    suspend fun login(username: String, password: String): LoginResponse =
        post(base.withPath("api", "login"), Http.json.encodeToString(LoginRequest.serializer(), LoginRequest(username, password)))
            .let { Http.json.decodeFromString(LoginResponse.serializer(), it) }

    suspend fun sections(accessToken: String): List<Section> {
        val req = Request.Builder().url(base.withPath("api", "sections"))
            .header("Authorization", "Bearer $accessToken").get().build()
        return Http.json.decodeFromString(kotlinx.serialization.builtins.ListSerializer(Section.serializer()), http.send(req))
    }

    suspend fun grant(accessToken: String, sectionId: String): GrantResponse =
        post(base.withPath("api", "sections", sectionId, "grant"), "{}", accessToken)
            .let { Http.json.decodeFromString(GrantResponse.serializer(), it) }

    suspend fun postReceipt(receipt: String): ReceiptResponse =
        post(base.withPath("api", "attendance", "receipts"),
            Http.json.encodeToString(ReceiptRequest.serializer(), ReceiptRequest(receipt)))
            .let { Http.json.decodeFromString(ReceiptResponse.serializer(), it) }

    private suspend fun post(url: HttpUrl, body: String, bearer: String? = null): String {
        val req = Request.Builder().url(url).post(body.toRequestBody(JSON_TYPE))
            .apply { bearer?.let { header("Authorization", "Bearer $it") } }.build()
        return http.send(req)
    }
}

/**
 * Campus MEC. Every state-changing body is serialised once, signed with the
 * Keystore key, and sent as exactly those bytes.
 */
class MecClient(private val http: OkHttpClient, baseUrl: String, private val key: DeviceKey) {
    private val base = baseUrl.trim().trimEnd('/').toHttpUrl()

    suspend fun registerDevice(accessToken: String, label: String): String {
        val body = Http.json.encodeToString(RegisterDeviceBody.serializer(),
            RegisterDeviceBody(key.publicKeyPem(), label, now()))
        val resp = signedPost(base.withPath("devices"), body, accessToken)
        return Http.json.decodeFromString(RegisterDeviceResponse.serializer(), resp).device_id
    }

    suspend fun openSession(grantToken: String, deviceId: String): OpenSessionResponse {
        val body = Http.json.encodeToString(OpenSessionBody.serializer(), OpenSessionBody(deviceId, now()))
        return Http.json.decodeFromString(OpenSessionResponse.serializer(),
            signedPost(base.withPath("sessions"), body, grantToken))
    }

    suspend fun submit(
        deviceId: String, sessionId: String, nonce: String, present: List<String>,
        metrics: kotlinx.serialization.json.JsonObject?, evidence: Evidence?,
    ): SubmitResponse {
        val body = Http.json.encodeToString(SubmitBody.serializer(),
            SubmitBody(deviceId, sessionId, nonce, now(), present, metrics, evidence))
        return Http.json.decodeFromString(SubmitResponse.serializer(),
            signedPost(base.withPath("sessions", sessionId, "attendance"), body))
    }

    private suspend fun signedPost(url: HttpUrl, body: String, bearer: String? = null): String {
        val bytes = body.toByteArray(Charsets.UTF_8)
        val req = Request.Builder().url(url).post(bytes.toRequestBody(JSON_TYPE))
            .header("X-Signature", key.sign(bytes))
            .apply { bearer?.let { header("Authorization", "Bearer $it") } }.build()
        return http.send(req)
    }
}
