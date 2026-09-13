// Экран логина
package ru.smartkam.patrol.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import ru.smartkam.patrol.data.TokenStore
import ru.smartkam.patrol.data.api.ApiClient
import ru.smartkam.patrol.data.api.LoginRequest

@Composable
fun LoginScreen(onSuccess: () -> Unit) {
    var login by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var error by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Patrol", fontSize = 32.sp, color = MaterialTheme.colorScheme.primary)
        Text("Охранник", fontSize = 14.sp, color = MaterialTheme.colorScheme.secondary)
        androidx.compose.foundation.layout.Spacer(Modifier.padding(12.dp))
        OutlinedTextField(value = login, onValueChange = { login = it }, label = { Text("Логин") }, singleLine = true)
        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("Пароль") },
            visualTransformation = PasswordVisualTransformation(),
            singleLine = true,
        )
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, fontSize = 13.sp)
        androidx.compose.foundation.layout.Spacer(Modifier.padding(8.dp))
        Button(
            onClick = {
                busy = true; error = ""
                scope.launch {
                    try {
                        val t = ApiClient.api.login(LoginRequest(login, password))
                        val store = TokenStore.get()
                        store.access = t.access; store.refresh = t.refresh; store.userName = t.fullName
                        onSuccess()
                    } catch (e: Exception) {
                        error = "Ошибка входа: проверьте логин/пароль и сеть"
                    } finally {
                        busy = false
                    }
                }
            },
            enabled = !busy && login.isNotEmpty() && password.isNotEmpty(),
        ) {
            if (busy) CircularProgressIndicator(Modifier.padding(4.dp))
            else Text("Войти")
        }
    }
}
