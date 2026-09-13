// Сканер QR: CameraX + ML Kit, результат офлайн-валидации крупно
package ru.smartkam.patrol.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import kotlinx.coroutines.launch
import ru.smartkam.patrol.data.AppGraph
import ru.smartkam.patrol.data.ScanOutcome
import ru.smartkam.patrol.data.ScanVerdict
import java.util.concurrent.Executors

@Composable
fun ScannerScreen(patrolId: Long, onClose: () -> Unit) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val graph = AppGraph.get(context)
    val repo = graph.repository

    var hasCamera by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED
        )
    }
    val permLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        hasCamera = it
    }
    if (!hasCamera) {
        Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally) {
            Spacer(Modifier.height(32.dp))
            Text("Нужен доступ к камере", fontSize = 18.sp)
            Button(onClick = { permLauncher.launch(Manifest.permission.CAMERA) }) { Text("Разрешить") }
            Button(onClick = onClose) { Text("Назад") }
        }
        return
    }

    var outcome by remember { mutableStateOf<ScanOutcome?>(null) }
    var lastCode by remember { mutableStateOf("") }
    val analysisExecutor = remember { Executors.newSingleThreadExecutor() }
    DisposableEffect(Unit) {
        onDispose { analysisExecutor.shutdown() }
    }

    // свежий скан не чаще раза в 1.5 сек на тот же код
    var lastScanAt by remember { mutableStateOf(0L) }

    Column(Modifier.fillMaxSize()) {
        Box(Modifier.weight(1f).fillMaxWidth()) {
            AndroidView(
                factory = { ctx ->
                    val previewView = PreviewView(ctx)
                    val providerFuture = ProcessCameraProvider.getInstance(ctx)
                    providerFuture.addListener({
                        val provider = providerFuture.get()
                        val preview = Preview.Builder().build().also {
                            it.setSurfaceProvider(previewView.surfaceProvider)
                        }
                        val options = BarcodeScannerOptions.Builder()
                            .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
                            .build()
                        val scanner = BarcodeScanning.getClient(options)
                        val analysis = ImageAnalysis.Builder()
                            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                            .build()
                        analysis.setAnalyzer(analysisExecutor) { imageProxy ->
                            @androidx.camera.core.ExperimentalGetImage
                            val mediaImage = imageProxy.image
                            if (mediaImage != null) {
                                val input = InputImage.fromMediaImage(
                                    mediaImage, imageProxy.imageInfo.rotationDegrees,
                                )
                                scanner.process(input)
                                    .addOnSuccessListener { barcodes ->
                                        val code = barcodes.firstOrNull()?.rawValue
                                        if (code != null && code != lastCode &&
                                            System.currentTimeMillis() - lastScanAt > 1500
                                        ) {
                                            lastScanAt = System.currentTimeMillis()
                                            lastCode = code
                                            graph.scope.launch {
                                                outcome = repo.handleScan(code)
                                            }
                                        }
                                    }
                                    .addOnCompleteListener { imageProxy.close() }
                            } else {
                                imageProxy.close()
                            }
                        }
                        provider.unbindAll()
                        provider.bindToLifecycle(
                            lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis,
                        )
                    }, ContextCompat.getMainExecutor(ctx))
                    previewView
                },
                modifier = Modifier.fillMaxSize(),
            )
        }

        // Результат последнего скана
        Box(
            Modifier.fillMaxWidth().background(Color(0xFF0B0F14)).padding(16.dp),
            contentAlignment = Alignment.Center,
        ) {
            val o = outcome
            when {
                o == null -> Text("Наведите камеру на QR-код точки", color = Color.White, fontSize = 16.sp)
                o.verdict == ScanVerdict.ACCEPTED -> Text(
                    "✓ ${o.message}", color = Color(0xFF4ADE80), fontSize = 18.sp,
                )
                o.verdict == ScanVerdict.DUPLICATE -> Text(
                    "= ${o.message}", color = Color(0xFFFACC15), fontSize = 16.sp,
                )
                else -> Text(
                    "✗ ${o.message}", color = Color(0xFFF87171), fontSize = 16.sp,
                )
            }
        }
        Row(
            Modifier.fillMaxWidth().padding(12.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            Button(onClick = {
                graph.scope.launch {
                    repo.pushQueue()
                }
                onClose()
            }) { Text("Готово") }
        }
    }
}
