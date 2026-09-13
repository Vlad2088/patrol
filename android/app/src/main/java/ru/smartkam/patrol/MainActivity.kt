// Точка входа: навигация между экранами
package ru.smartkam.patrol

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import ru.smartkam.patrol.data.TokenStore
import ru.smartkam.patrol.ui.screens.HistoryScreen
import ru.smartkam.patrol.ui.screens.LoginScreen
import ru.smartkam.patrol.ui.screens.PatrolListScreen
import ru.smartkam.patrol.ui.screens.PatrolProgressScreen
import ru.smartkam.patrol.ui.screens.ScannerScreen
import ru.smartkam.patrol.ui.theme.PatrolTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val tokens = TokenStore.get(applicationContext)
        setContent {
            PatrolTheme {
                AppNav(startLoggedIn = tokens.isLoggedIn)
            }
        }
    }
}

@Composable
fun AppNav(startLoggedIn: Boolean) {
    val nav = rememberNavController()
    val start = if (startLoggedIn) "patrols" else "login"
    NavHost(navController = nav, startDestination = start) {
        composable("login") {
            LoginScreen(onSuccess = {
                nav.navigate("patrols") { popUpTo("login") { inclusive = true } }
            })
        }
        composable("patrols") {
            PatrolListScreen(
                onOpenPatrol = { nav.navigate("progress/$it") },
                onOpenScanner = { nav.navigate("scan/$it") },
                onHistory = { nav.navigate("history") },
            )
        }
        composable("scan/{patrolId}") { entry ->
            ScannerScreen(
                patrolId = entry.arguments?.getString("patrolId")?.toLongOrNull() ?: return@composable,
                onClose = { nav.popBackStack() },
            )
        }
        composable("progress/{patrolId}") { entry ->
            PatrolProgressScreen(
                patrolId = entry.arguments?.getString("patrolId")?.toLongOrNull() ?: return@composable,
                onScan = { pid -> nav.navigate("scan/$pid") },
                onBack = { nav.popBackStack() },
            )
        }
        composable("history") {
            HistoryScreen(onBack = { nav.popBackStack() })
        }
    }
}
