// Retrofit-клиент с JWT-интерцептором и авто-refresh
package ru.smartkam.patrol.data.api

import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import ru.smartkam.patrol.BuildConfig
import ru.smartkam.patrol.data.TokenStore

class AuthInterceptor(private val tokens: TokenStore) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = tokens.access
        val req = if (token.isNotEmpty()) {
            chain.request().newBuilder().header("Authorization", "Bearer $token").build()
        } else chain.request()
        val res = chain.proceed(req)
        if (res.code == 401 && tokens.refresh.isNotEmpty()) {
            res.close()
            val newAccess = runBlocking {
                try {
                    apiForRefresh().refresh(RefreshRequest(tokens.refresh)).access
                } catch (_: Exception) {
                    return@runBlocking null
                }
            }
            if (newAccess != null) {
                tokens.access = newAccess
                val retried = chain.request().newBuilder()
                    .header("Authorization", "Bearer $newAccess").build()
                return chain.proceed(retried)
            }
        }
        return res
    }

    private fun apiForRefresh(): PatrolApi = Retrofit.Builder()
        .baseUrl("${BuildConfig.API_BASE}/")
        .addConverterFactory(GsonConverterFactory.create())
        .build().create(PatrolApi::class.java)
}

object ApiClient {
    val api: PatrolApi by lazy {
        val client = OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor(TokenStore.get()))
            .build()
        Retrofit.Builder()
            .baseUrl("${BuildConfig.API_BASE}/")
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(PatrolApi::class.java)
    }
}
