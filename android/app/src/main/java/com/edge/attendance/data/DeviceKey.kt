package com.edge.attendance.data

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.Signature
import java.security.spec.ECGenParameterSpec

/**
 * The phone's identity: an EC P-256 key generated inside Android Keystore.
 * The private key never leaves secure hardware; the MEC stores the public
 * key and verifies every request signature against it.
 */
class DeviceKey(private val alias: String = "attendance_device_key") {
    private val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }

    private fun entry(): KeyStore.PrivateKeyEntry {
        if (!keyStore.containsAlias(alias)) generate()
        return keyStore.getEntry(alias, null) as KeyStore.PrivateKeyEntry
    }

    private fun generate() {
        val generator = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, ANDROID_KEYSTORE)
        generator.initialize(
            KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_SIGN)
                .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
                .setDigests(KeyProperties.DIGEST_SHA256)
                .build()
        )
        generator.generateKeyPair()
    }

    /** SubjectPublicKeyInfo PEM, the format the MEC expects. */
    fun publicKeyPem(): String {
        val der = entry().certificate.publicKey.encoded
        val body = Base64.encodeToString(der, Base64.NO_WRAP).chunked(64).joinToString("\n")
        return "-----BEGIN PUBLIC KEY-----\n$body\n-----END PUBLIC KEY-----\n"
    }

    /** SHA256withECDSA over [data]; base64 of the DER signature (X-Signature header). */
    fun sign(data: ByteArray): String {
        val signature = Signature.getInstance("SHA256withECDSA")
        signature.initSign(entry().privateKey)
        signature.update(data)
        return Base64.encodeToString(signature.sign(), Base64.NO_WRAP)
    }

    private companion object {
        const val ANDROID_KEYSTORE = "AndroidKeyStore"
    }
}
