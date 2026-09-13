// Room: офлайн-копия справочников + очередь сканов
package ru.smartkam.patrol.data.db

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase

@Entity(tableName = "routes")
data class RouteEntity(
    @PrimaryKey val id: Long,
    val objectId: Long,
    val name: String,
)

@Entity(tableName = "checkpoints")
data class CheckpointEntity(
    @PrimaryKey val id: Long,
    val routeId: Long,
    val orderNum: Int,
    val code: String,
    val name: String?,
)

@Entity(tableName = "patrols")
data class PatrolEntity(
    @PrimaryKey val id: Long,
    val objectId: Long,
    val routeId: Long,
    val windowStart: String,
    val windowEnd: String,
    val status: String,
    val checkpointsTotal: Int,
    val checkpointsScanned: Int,
)

@Entity(tableName = "shifts")
data class ShiftEntity(
    @PrimaryKey val id: Long,
    val objectId: Long,
    val startsAt: String,
    val endsAt: String,
)

@Entity(tableName = "scans")
data class ScanQueueEntity(
    @PrimaryKey val clientUuid: String,
    val patrolId: Long,
    val checkpointCode: String,
    val scannedAt: String,
    val syncState: String = "pending", // pending | done | error
    val serverResult: String? = null,
)

@Entity(tableName = "scanned_checkpoints")
data class ScannedCheckpointEntity(
    @PrimaryKey val patrolIdCheckpointId: String, // "$patrolId:$checkpointId"
    val patrolId: Long,
    val checkpointId: Long,
    val scannedAt: String,
)

@Dao
interface PatrolDao {
    @Query("DELETE FROM routes") suspend fun clearRoutes()
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun insertRoutes(items: List<RouteEntity>)
    @Query("SELECT * FROM routes ORDER BY name") suspend fun routes(): List<RouteEntity>
    @Query("SELECT * FROM routes WHERE id = :id LIMIT 1") suspend fun routeById(id: Long): RouteEntity?

    @Query("DELETE FROM checkpoints") suspend fun clearCheckpoints()
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun insertCheckpoints(items: List<CheckpointEntity>)
    @Query("SELECT * FROM checkpoints WHERE routeId = :routeId ORDER BY orderNum") suspend fun checkpointsOf(routeId: Long): List<CheckpointEntity>
    @Query("SELECT * FROM checkpoints WHERE code = :code LIMIT 1") suspend fun checkpointByCode(code: String): CheckpointEntity?

    @Query("DELETE FROM patrols") suspend fun clearPatrols()
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun insertPatrols(items: List<PatrolEntity>)
    @Query("SELECT * FROM patrols WHERE status IN ('planned','in_progress') ORDER BY windowStart") suspend fun activePatrols(): List<PatrolEntity>
    @Query("SELECT * FROM patrols ORDER BY windowStart DESC LIMIT 100") suspend fun allPatrols(): List<PatrolEntity>
    @Query("SELECT * FROM patrols WHERE id = :id LIMIT 1") suspend fun patrol(id: Long): PatrolEntity?

    @Query("DELETE FROM shifts") suspend fun clearShifts()
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun insertShifts(items: List<ShiftEntity>)
    @Query("SELECT * FROM shifts ORDER BY startsAt") suspend fun shifts(): List<ShiftEntity>

    @Insert(onConflict = OnConflictStrategy.IGNORE) suspend fun enqueueScan(item: ScanQueueEntity)
    @Query("SELECT * FROM scans WHERE syncState = 'pending' ORDER BY scannedAt LIMIT 50") suspend fun pendingScans(): List<ScanQueueEntity>
    @Query("UPDATE scans SET syncState = :state, serverResult = :result WHERE clientUuid = :uuid") suspend fun updateScan(uuid: String, state: String, result: String?)
    @Query("SELECT COUNT(*) FROM scans WHERE syncState = 'pending'") suspend fun pendingCount(): Int

    @Insert(onConflict = OnConflictStrategy.IGNORE) suspend fun markScanned(item: ScannedCheckpointEntity)
    @Query("SELECT checkpointId FROM scanned_checkpoints WHERE patrolId = :patrolId") suspend fun scannedIds(patrolId: Long): List<Long>
    @Query("SELECT COUNT(*) FROM scanned_checkpoints WHERE patrolId = :patrolId") suspend fun scannedCount(patrolId: Long): Int
}

@Database(
    entities = [
        RouteEntity::class, CheckpointEntity::class, PatrolEntity::class,
        ShiftEntity::class, ScanQueueEntity::class, ScannedCheckpointEntity::class,
    ],
    version = 1,
)
abstract class PatrolDatabase : RoomDatabase() {
    abstract fun dao(): PatrolDao
}
