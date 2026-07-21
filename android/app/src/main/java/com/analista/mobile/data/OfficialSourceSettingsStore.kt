package com.analista.mobile.data

import android.content.Context
import android.util.Base64
import java.nio.charset.StandardCharsets
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties

class OfficialSourceSettingsStore(context: Context) {
    data class Settings(
        val fredApiKey: String?,
        val secContactEmail: String?
    )

    private val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun load(): Settings = Settings(
        fredApiKey = decryptOrNull(prefs.getString(KEY_FRED, null)),
        secContactEmail = decryptOrNull(prefs.getString(KEY_SEC_EMAIL, null))
    )

    fun saveFredApiKey(value: String) {
        val normalized = value.trim()
        require(normalized.isNotBlank())
        prefs.edit().putString(KEY_FRED, encrypt(normalized)).apply()
    }

    fun saveSecContactEmail(value: String) {
        val normalized = value.trim().lowercase()
        require(EMAIL.matches(normalized)) { "Correo SEC inválido" }
        prefs.edit().putString(KEY_SEC_EMAIL, encrypt(normalized)).apply()
    }

    fun clearFredApiKey() = prefs.edit().remove(KEY_FRED).apply()
    fun clearSecContactEmail() = prefs.edit().remove(KEY_SEC_EMAIL).apply()
    fun clearAll() = prefs.edit().clear().apply()

    private fun encrypt(value: String): String {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey())
        val encrypted = cipher.doFinal(value.toByteArray(StandardCharsets.UTF_8))
        return Base64.encodeToString(cipher.iv + encrypted, Base64.NO_WRAP)
    }

    private fun decryptOrNull(payload: String?): String? = runCatching {
        if (payload.isNullOrBlank()) return@runCatching null
        val bytes = Base64.decode(payload, Base64.NO_WRAP)
        if (bytes.size <= IV_BYTES) return@runCatching null
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(), GCMParameterSpec(128, bytes.copyOfRange(0, IV_BYTES)))
        String(cipher.doFinal(bytes.copyOfRange(IV_BYTES, bytes.size)), StandardCharsets.UTF_8)
    }.getOrNull()

    private fun getOrCreateKey(): SecretKey {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (keyStore.getKey(ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(
            KeyGenParameterSpec.Builder(
                ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build()
        )
        return generator.generateKey()
    }

    companion object {
        private const val PREFS = "official_source_settings_v1"
        private const val KEY_FRED = "fred_api_key"
        private const val KEY_SEC_EMAIL = "sec_contact_email"
        private const val ALIAS = "analista_official_sources_v1"
        private const val TRANSFORMATION = "AES/GCM/NoPadding"
        private const val IV_BYTES = 12
        private val EMAIL = Regex("^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$")
    }
}
