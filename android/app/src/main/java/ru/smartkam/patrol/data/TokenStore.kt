// Хранилище токенов (простое, на SharedPreferences; прод: EncryptedSharedPreferences)
package ru.smartkam.patrol.data

import android.content.Context
import android.content.SharedPreferences

class TokenStore private constructor(private val prefs: SharedPreferences) {
    var access: String
        get() = prefs.getString(K_ACCESS, "") ?: ""
        set(v) = prefs.edit().putString(K_ACCESS, v).apply()
    var refresh: String
        get() = prefs.getString(K_REFRESH, "") ?: ""
        set(v) = prefs.edit().putString(K_REFRESH, v).apply()
    var userName: String
        get() = prefs.getString(K_NAME, "") ?: ""
        set(v) = prefs.edit().putString(K_NAME, v).apply()

    val isLoggedIn: Boolean get() = refresh.isNotEmpty()

    fun clear() = prefs.edit().clear().apply()

    companion object {
        private const val K_ACCESS = "access"
        private const val K_REFRESH = "refresh"
        private const val K_NAME = "name"
        @Volatile private var inst: TokenStore? = null

        fun get(ctx: Context? = null): TokenStore {
            return inst ?: synchronized(this) {
                inst ?: TokenStore(
                    ctx!!.applicationContext.getSharedPreferences("patrol_tokens", Context.MODE_PRIVATE)
                ).also { inst = it }
            }
        }
    }
}
