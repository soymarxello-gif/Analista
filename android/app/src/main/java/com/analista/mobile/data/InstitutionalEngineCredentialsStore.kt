package com.analista.mobile.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.io.File
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class InstitutionalEngineCredentialsStore(context: Context) {
    data class Credentials(val baseUrl: String, val bearerToken: String)

    private val file = File(context.noBackupFilesDir, "institutional_engine_credentials.dat")
    private val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }

    fun save(credentials: Credentials) {
        val url = credentials.baseUrl.trim().trimEnd('/')
        val localDevelopment = url.startsWith("http://127.0.0.1") || url.startsWith("http://10.0.2.2")
        require(url.startsWith("https://") || localDevelopment) {
            "El motor requiere HTTPS; HTTP solo se permite en localhost/emulador"
        }
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val plaintext = "$url\n${credentials.bearerToken.trim()}"
        val payload = Base64.encodeToString(cipher.iv, Base64.NO_WRAP) + ":" +
            Base64.encodeToString(cipher.doFinal(plaintext.toByteArray()), Base64.NO_WRAP)
        file.writeText(payload)
    }

    fun load(): Credentials? = if (!file.exists()) null else runCatching {
        val parts = file.readText().split(":", limit = 2)
        require(parts.size == 2)
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(
            Cipher.DECRYPT_MODE,
            key(),
            GCMParameterSpec(128, Base64.decode(parts[0], Base64.NO_WRAP))
        )
        val values = String(cipher.doFinal(Base64.decode(parts[1], Base64.NO_WRAP))).split("\n", limit = 2)
        Credentials(values[0], values.getOrElse(1) { "" })
    }.getOrNull()

    fun clear() { file.delete() }
    fun isConfigured() = load() != null

    private fun key(): SecretKey {
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").run {
            init(
                KeyGenParameterSpec.Builder(KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build()
            )
            generateKey()
        }
    }

    companion object {
        private const val KEY_ALIAS = "analista_institutional_engine_v1"
        private const val TRANSFORMATION = "AES/GCM/NoPadding"
    }
}
