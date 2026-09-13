// Список активных обходов + синк + выход
package ru.smartkam.patrol.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import ru.smartkam.patrol.data.AppGraph
import ru.smartkam.patrol.data.TokenStore
import ru.smartkam.patrol.data.db.PatrolEntity
import ru.smartkam.patrol.data.db.RouteEntity
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

private val fmt = DateTimeFormatter.ISO_DATE_TIME

@Composable
fun PatrolListScreen(
    onOpenPatrol: (Long) -> Unit,
    onOpenScanner: (Long) -> Unit,
    onHistory: () -> Unit,
) {
    val graph = AppGraph.get(LocalContext.current)
    val repo = graph.repository
    var patrols by remember { mutableStateOf<List<Pair<PatrolEntity, RouteEntity?>>>(emptyList()) }
    var syncing by remember { mutableStateOf(false) }
    var pending by remember { mutableStateOf(0) }
    var message by remember { mutableStateOf("") }
    var loggedOut by remember { mutableStateOf(false) }

    fun refresh() {
        graph.scope.launch {
            patrols = graph.activePatrolsWithRoutes()
            pending = repo.pendingCount()
        }
    }

    LaunchedEffect(Unit) { refresh() }

    if (loggedOut) {
        LoginScreen(onSuccess = {
            loggedOut = false
            refresh()
        })
        return
    }

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("Обходы", fontSize = 22.sp)
            TextButton(onClick = onHistory) { Text("История") }
        }
        Text(
            TokenStore.get().userName,
            fontSize = 13.sp,
            color = MaterialTheme.colorScheme.secondary,
        )
        Row(Modifier.padding(vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = {
                    syncing = true; message = ""
                    graph.scope.launch {
                        message = try {
                            repo.fullSync(); refresh(); "Синхронизация OK"
                        } catch (_: Exception) {
                            "Нет сети: работаем офлайн (${pending} отметок в очереди)"
                        }
                        syncing = false
                    }
                },
                enabled = !syncing,
            ) { Text(if (syncing) "Синк..." else "Синхронизировать") }
            OutlinedButton(onClick = {
                graph.scope.launch {
                    val n = repo.pushQueue()
                    pending = repo.pendingCount()
                    message = if (n > 0) "Отправлено отметок: $n" else "Очередь пуста или нет сети"
                }
            }) { Text("Отправить (${pending})") }
            TextButton(onClick = {
                TokenStore.get().clear()
                loggedOut = true
            }) { Text("Выйти") }
        }
        if (message.isNotEmpty()) Text(message, fontSize = 13.sp, color = MaterialTheme.colorScheme.primary)

        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(patrols) { (p, route) ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp)) {
                        Text(route?.name ?: "Маршрут #${p.routeId}", fontSize = 17.sp)
                        Text(
                            "Окно: ${p.windowStart.fmtShort()} – ${p.windowEnd.fmtShort()}",
                            fontSize = 13.sp, color = MaterialTheme.colorScheme.secondary,
                        )
                        Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(onClick = {
                                graph.scope.launch {
                                    message = repo.startPatrol(p.id)
                                    refresh()
                                }
                                onOpenScanner(p.id)
                            }) { Text("Начать / сканировать") }
                            OutlinedButton(onClick = { onOpenPatrol(p.id) }) { Text("Прогресс") }
                        }
                    }
                }
            }
        }
    }
}

private fun String.fmtShort(): String = try {
    LocalDateTime.parse(this, fmt).format(DateTimeFormatter.ofPattern("HH:mm"))
} catch (_: Exception) {
    this
}
