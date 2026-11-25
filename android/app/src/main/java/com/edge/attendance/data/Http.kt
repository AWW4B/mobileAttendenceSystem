package com.edge.attendance.data

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException
import java.security.KeyStore
import java.security.MessageDigest
import java.security.cert.CertificateException
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManagerFactory
import javax.net.ssl.X509TrustManager

class ApiException(val code: Int, message: String) : IOException(message)

object Http {
    val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
    }

    /** The MEC's self-signed certificate, copied in at build time (see app/build.gradle.kts). */
    private const val PINNED_CERT_ASSET = "mec_cert.pem"

    @Volatile private var client: OkHttpClient? = null

    fun client(context: Context): OkHttpClient =
        client ?: synchronized(this) {
            client ?: build(context.applicationContext).also { client = it }
        }

    private fun build(context: Context): OkHttpClient {
        val builder = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .callTimeout(60, TimeUnit.SECONDS)
        val prefs = AppPrefs(context)
        val tm = trustManager(context) { prefs.serverCode }
        val ssl = SSLContext.getInstance("TLS").apply { init(null, arrayOf(tm), null) }
        builder.sslSocketFactory(ssl.socketFactory, tm)
        return builder.build()
    }

    /**
     * Trusts the certificate matching the typed server code (so one APK works with any
     * laptop), else the certificate bundled at build time, else the system CAs.
     * Host names are still verified by OkHttp in every case.
     */
    private fun trustManager(context: Context, serverCode: () -> String): X509TrustManager {
        val certs = try {
            context.assets.open(PINNED_CERT_ASSET).use {
                CertificateFactory.getInstance("X.509").generateCertificates(it)
            }
        } catch (e: IOException) {
            emptyList()
        }
        val system = trustManagerFor(null)
        val pinned = if (certs.isEmpty()) null else trustManagerFor(
            KeyStore.getInstance(KeyStore.getDefaultType()).apply {
                load(null, null)
                certs.forEachIndexed { i, c -> setCertificateEntry("pinned$i", c) }
            },
        )
        return object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) =
                system.checkClientTrusted(chain, authType)

            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {
                if (matchesServerCode(chain[0].encoded, serverCode())) return chain[0].checkValidity()
                try {
                    (pinned ?: system).checkServerTrusted(chain, authType)
                } catch (e: CertificateException) {
                    system.checkServerTrusted(chain, authType)
                }
            }

            override fun getAcceptedIssuers(): Array<X509Certificate> =
                (pinned?.acceptedIssuers ?: emptyArray()) + system.acceptedIssuers
        }
    }

    /** True when [code] (at least 16 hex digits; separators ignored) starts the certificate's SHA-256. */
    fun matchesServerCode(der: ByteArray, code: String): Boolean {
        val wanted = code.lowercase().filter { it in "0123456789abcdef" }
        if (wanted.length < 16) return false
        val actual = MessageDigest.getInstance("SHA-256").digest(der).joinToString("") { "%02x".format(it) }
        return actual.startsWith(wanted)
    }

    private fun trustManagerFor(store: KeyStore?): X509TrustManager {
        val factory = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm())
        factory.init(store)
        return factory.trustManagers.filterIsInstance<X509TrustManager>().first()
    }
}

/** Execute on the IO dispatcher; return the body or throw [ApiException] with the server's detail. */
suspend fun OkHttpClient.send(request: Request): String = withContext(Dispatchers.IO) {
    newCall(request).execute().use { response ->
        val body = response.body?.string().orEmpty()
        if (!response.isSuccessful) {
            val detail = runCatching {
                Http.json.parseToJsonElement(body).jsonObject["detail"]?.jsonPrimitive?.content
            }.getOrNull()
            throw ApiException(response.code, detail ?: "HTTP ${response.code}")
        }
        body
    }
}
