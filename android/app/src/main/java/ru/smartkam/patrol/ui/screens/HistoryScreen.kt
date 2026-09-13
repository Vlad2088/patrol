// История своих обходов (сервер + локальные статусы)
package ru.smartkam.patrol.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
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
import ru.smartkam.patrol.data.api.ApiPatrol

private val STATUS_LABEL = mapOf(
    "planned" to "Запланирован",
    "in_progress" to "Идёт",
    "completed" to "Завершён",
    "missed" to "Пропущен",
    "partial" to "Частично",
)

@Composable
fun HistoryScreen(onBack: () -> Unit) {
    val graph = AppGraph.get(LocalContext.current)
    var patrols by remember { mutableStateOf<List<ApiPatrol>>(emptyList()) }
    var offline by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        graph.scope.launch {
            patrols = try {
                ru.smartkam.patrol.data.api.ApiClient.api.history()
            } catch (_: Exception) {
                offline = true
                emptyList()
            }
        }
    }

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            TextButton(onClick = onBack) { Text("← Назад") }
            Text("История обходов", fontSize = 20.sp)
        }
        if (offline) {
            Text(
                "Нет сети — история доступна только онлайн",
                color = MaterialTheme.colorScheme.secondary,
            )
        }
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(patrols) { p ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text("Обход #${p.id} — ${STATUS_LABEL[p.status] ?: p.status}", fontSize = 16.sp)
                        Text(
                            "Точки: ${p.checkpointsScanned}/${p.checkpointsTotal} · " +
                                "Окно: ${p.windowStart.take(16).replace('T', ' ')}",
                            fontSize = 13.sp,
                            color = MaterialTheme.colorScheme.secondary,
                        )
                    }
                }
            }
        }
    }
}
