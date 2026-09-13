// Глобальный граф зависимостей (простой service-locator)
package ru.smartkam.patrol.data

import android.content.Context
import androidx.room.Room
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import ru.smartkam.patrol.data.db.PatrolDatabase
import ru.smartkam.patrol.data.db.PatrolEntity
import ru.smartkam.patrol.data.db.RouteEntity

class AppGraph private constructor(db: PatrolDatabase) {
    val scope = CoroutineScope(Dispatchers.Main)
    val repository = PatrolRepository(db.dao())

    suspend fun activePatrolsWithRoutes(): List<Pair<PatrolEntity, RouteEntity?>> =
        repository.dao.activePatrols().map { p ->
            p to repository.dao.routeById(p.routeId)
        }

    companion object {
        @Volatile private var inst: AppGraph? = null

        fun get(ctx: Context): AppGraph =
            inst ?: synchronized(this) {
                inst ?: AppGraph(
                    Room.databaseBuilder(
                        ctx.applicationContext,
                        PatrolDatabase::class.java,
                        "patrol.db",
                    ).fallbackToDestructiveMigration().build()
                ).also { inst = it }
            }
    }
}
