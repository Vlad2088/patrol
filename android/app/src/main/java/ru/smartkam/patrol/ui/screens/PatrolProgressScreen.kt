// Прогресс обхода: сколько пройдено, следующая точка, кнопка скана
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
import androidx.compose.material3.CardDefaults
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
import ru.smartkam.patrol.data.db.CheckpointEntity

@Composable
fun PatrolProgressScreen(patrolId: Long, onScan: (Long) -> Unit, onBack: () -> Unit) {
    val graph = AppGraph.get(LocalContext.current)
    val repo = graph.repository
    var checkpoints by remember { mutableStateOf<List<Pair<CheckpointEntity, Boolean>>>(emptyList()) }
    var routeName by remember { mutableStateOf("") }

    fun refresh() {
        graph.scope.launch {
            val patrol = repo.dao.patrol(patrolId) ?: return@launch
            val route = repo.dao.routeById(patrol.routeId)
            routeName = route?.name ?: "Маршрут #${patrol.routeId}"
            val scanned = repo.dao.scannedIds(patrolId).toSet()
            checkpoints = repo.dao.checkpointsOf(patrol.routeId).map { it to (it.id in scanned) }
        }
    }

    LaunchedEffect(patrolId) { refresh() }

    val done = checkpoints.count { it.second }

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            TextButton(onClick = onBack) { Text("← Назад") }
            Text("$routeName: $done / ${checkpoints.size}", fontSize = 20.sp)
        }

        Button(
            onClick = { onScan(patrolId) },
            modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp),
        ) { Text("Сканировать следующую точку", fontSize = 16.sp) }

        LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            items(checkpoints) { (cp, isDone) ->
                Card(
                    Modifier.fillMaxWidth(),
                    colors = if (isDone) CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.primary,
                    ) else CardDefaults.cardColors(),
                ) {
                    Row(Modifier.padding(12.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("${cp.orderNum}. ${cp.name ?: cp.code}")
                        Text(if (isDone) "✓" else "•")
                    }
                }
            }
        }
    }
}
