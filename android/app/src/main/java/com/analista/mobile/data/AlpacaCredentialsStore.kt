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

class AlpacaCredentialsStore(context: Context) {
    data class Credentials(val apiKey: String, val secretKey: String, val feed: String = "iex")

    private val file = File(context.noBackupFilesDir, "alpaca_credentials.dat")
    private val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }

    fun save(credentials: Credentials) {
        require(credentials.apiKey.isNotBlank())
        require(credentials.secretKey.isNotBlank())
        require(credentials.feed in ALLOWED_FEEDS)
        val plaintext = listOf(credentials.apiKey.trim(), credentials.secretKey.trim(), credentials.feed).joinToString("\n")
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey())
        val encrypted = cipher.doFinal(plaintext.toByteArray(Charsets.UTF_8))
        val payload = Base64.encodeToString(cipher.iv, Base64.NO_WRAP) + ":" +
            Base64.encodeToString(encrypted, Base64.NO_WRAP)
        file.writeText(payload)
    }

    fun load(): Credentials? {
        if (!file.exists()) return null
        return runCatching {
            val parts = file.readText().split(":", limit = 2)
            require(parts.size == 2)
            val iv = Base64.decode(parts[0], Base64.NO_WRAP)
            val encrypted = Base64.decode(parts[1], Base64.NO_WRAP)
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(), GCMParameterSpec(128, iv))
            val values = String(cipher.doFinal(encrypted), Charsets.UTF_8).split("\n")
            require(values.size == 3)
            Credentials(values[0], values[1], values[2].takeIf { it in ALLOWED_FEEDS } ?: "iex")
        }.getOrNull()
    }

    fun clear() {
        file.delete()
    }

    fun isConfigured(): Boolean = load() != null

    private fun getOrCreateKey(): SecretKey {
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build()
        )
        return generator.generateKey()
    }

    companion object {
        private const val KEY_ALIAS = "analista_alpaca_credentials_v1"
        private const val TRANSFORMATION = "AES/GCM/NoPadding"
        val ALLOWED_FEEDS = setOf("iex", "sip", "delayed_sip")
    }
}
