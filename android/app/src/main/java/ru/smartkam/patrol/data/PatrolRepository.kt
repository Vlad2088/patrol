// Репозиторий: синк, офлайн-валидация скана, отправка очереди
package ru.smartkam.patrol.data

import ru.smartkam.patrol.data.api.ApiClient
import ru.smartkam.patrol.data.api.ScanBatch
import ru.smartkam.patrol.data.api.ScanItem
import ru.smartkam.patrol.data.db.PatrolDao
import ru.smartkam.patrol.data.db.ScanQueueEntity
import ru.smartkam.patrol.data.db.ScannedCheckpointEntity
import java.time.Instant
import java.util.UUID

enum class ScanVerdict { ACCEPTED, DUPLICATE, WRONG_CHECKPOINT, OUT_OF_ORDER, NO_ACTIVE_PATROL }

data class ScanOutcome(val verdict: ScanVerdict, val message: String, val checkpointName: String? = null)

class PatrolRepository(val dao: PatrolDao) {

    suspend fun fullSync() {
        val data = ApiClient.api.sync()
        dao.clearRoutes(); dao.insertRoutes(data.routes.map { ru.smartkam.patrol.data.db.RouteEntity(it.id, it.objectId, it.name) })
        dao.clearCheckpoints(); dao.insertCheckpoints(data.checkpoints.map { ru.smartkam.patrol.data.db.CheckpointEntity(it.id, it.routeId, it.orderNum, it.code, it.name) })
        dao.clearPatrols(); dao.insertPatrols(data.patrols.map { ru.smartkam.patrol.data.db.PatrolEntity(it.id, it.objectId, it.routeId, it.windowStart, it.windowEnd, it.status, it.checkpointsTotal, it.checkpointsScanned) })
        dao.clearShifts(); dao.insertShifts(data.shifts.map { ru.smartkam.patrol.data.db.ShiftEntity(it.id, it.objectId, it.starts_at, it.ends_at) })
    }

    /** Офлайн-валидация + постановка в очередь (сервер перепроверит при синке). */
    suspend fun handleScan(code: String): ScanOutcome {
        val cp = dao.checkpointByCode(code)
            ?: return ScanOutcome(ScanVerdict.WRONG_CHECKPOINT, "Неизвестный QR-код: $code")

        val patrol = dao.activePatrols().firstOrNull { it.routeId == cp.routeId }
            ?: return ScanOutcome(ScanVerdict.NO_ACTIVE_PATROL, "Нет активного обхода для этой точки")

        val scanned = dao.scannedIds(patrol.id).toSet()

        // дубль?
        if (cp.id in scanned) {
            return ScanOutcome(ScanVerdict.DUPLICATE, "Точка «${cp.name ?: cp.code}» уже отмечена")
        }
        // порядок: все предыдущие должны быть отмечены
        val cps = dao.checkpointsOf(cp.routeId)
        val prior = cps.filter { it.orderNum < cp.orderNum }
        if (prior.any { it.id !in scanned }) {
            val nextExpected = cps.first { it.id !in scanned }
            return ScanOutcome(
                ScanVerdict.OUT_OF_ORDER,
                "Нарушен порядок! Следующая точка: ${nextExpected.orderNum}. ${nextExpected.name ?: nextExpected.code}",
            )
        }

        val uuid = UUID.randomUUID().toString()
        val now = Instant.now().toString()
        dao.enqueueScan(ScanQueueEntity(uuid, patrol.id, code, now))
        dao.markScanned(ScannedCheckpointEntity("${patrol.id}:${cp.id}", patrol.id, cp.id, now))
        return ScanOutcome(ScanVerdict.ACCEPTED, "Отмечено: ${cp.name ?: cp.code}", cp.name)
    }

    /** Отправка очереди (пачки по 50). Возвращает число отправленных. */
    suspend fun pushQueue(): Int {
        var sent = 0
        while (true) {
            val batch = dao.pendingScans()
            if (batch.isEmpty()) break
            val items = batch.map { ScanItem(it.clientUuid, it.checkpointCode, it.scannedAt) }
            val results = try {
                ApiClient.api.submitScans(ScanBatch(items))
            } catch (e: Exception) {
                break // сети нет — попробуем позже
            }
            for (r in results) {
                dao.updateScan(r.clientUuid, if (r.result == "accepted" || r.result == "out_of_window" || r.result == "duplicate") "done" else "error", r.result)
            }
            sent += items.size
        }
        return sent
    }

    suspend fun startPatrol(patrolId: Long): String {
        return try {
            val r = ApiClient.api.startPatrol(patrolId)
            if (r.ok) "" else r.message.ifEmpty { "Нельзя начать: ${r.message}" }
        } catch (e: Exception) {
            "Нет сети — обход начат офлайн, отметки накопятся и уйдут при синхронизации"
        }
    }

    suspend fun pendingCount(): Int = dao.pendingCount()
    suspend fun scannedCount(patrolId: Long): Int = dao.scannedCount(patrolId)
}
