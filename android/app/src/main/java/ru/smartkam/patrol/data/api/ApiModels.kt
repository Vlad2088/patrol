// Модель данных API (зеркало backend-схем)
package ru.smartkam.patrol.data.api

import com.google.gson.annotations.SerializedName
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

data class LoginRequest(val login: String, val password: String)
data class TokenPair(
    val access: String,
    val refresh: String,
    val role: String,
    @SerializedName("full_name") val fullName: String,
)
data class RefreshRequest(val refresh: String)
data class AccessResponse(val access: String)

data class ApiRoute(val id: Long, @SerializedName("object_id") val objectId: Long, val name: String)
data class ApiCheckpoint(
    val id: Long,
    @SerializedName("route_id") val routeId: Long,
    @SerializedName("order_num") val orderNum: Int,
    val code: String,
    val name: String?,
)
data class ApiPatrol(
    val id: Long,
    @SerializedName("object_id") val objectId: Long,
    @SerializedName("route_id") val routeId: Long,
    @SerializedName("window_start") val windowStart: String,
    @SerializedName("window_end") val windowEnd: String,
    val status: String,
    @SerializedName("checkpoints_total") val checkpointsTotal: Int,
    @SerializedName("checkpoints_scanned") val checkpointsScanned: Int,
)
data class ApiShift(val id: Long, @SerializedName("object_id") val objectId: Long, val starts_at: String, val ends_at: String)
data class SyncResponse(
    val routes: List<ApiRoute>,
    val checkpoints: List<ApiCheckpoint>,
    val patrols: List<ApiPatrol>,
    val shifts: List<ApiShift>,
)

data class ScanItem(
    @SerializedName("client_uuid") val clientUuid: String,
    @SerializedName("checkpoint_code") val checkpointCode: String,
    @SerializedName("scanned_at") val scannedAt: String, // ISO-8601 UTC
)
data class ScanBatch(val scans: List<ScanItem>)
data class ScanResultItem(
    @SerializedName("client_uuid") val clientUuid: String,
    val result: String,
    val message: String,
)
data class PatrolStartResponse(val ok: Boolean, val patrol: ApiPatrol?, val message: String)

interface PatrolApi {
    @POST("api/v1/auth/login")
    suspend fun login(@Body body: LoginRequest): TokenPair

    @POST("api/v1/auth/refresh")
    suspend fun refresh(@Body body: RefreshRequest): AccessResponse

    @GET("api/v1/mobile/sync")
    suspend fun sync(): SyncResponse

    @POST("api/v1/mobile/patrols/{id}/start")
    suspend fun startPatrol(@Path("id") id: Long): PatrolStartResponse

    @POST("api/v1/mobile/scans")
    suspend fun submitScans(@Body body: ScanBatch): List<ScanResultItem>

    @POST("api/v1/mobile/patrols/{id}/finish")
    suspend fun finishPatrol(@Path("id") id: Long): PatrolStartResponse

    @GET("api/v1/mobile/history")
    suspend fun history(): List<ApiPatrol>
}
