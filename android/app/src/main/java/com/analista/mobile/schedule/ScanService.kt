package com.analista.mobile.schedule

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.analista.mobile.AnalistaApplication
import com.analista.mobile.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class ScanService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val channelId = "analista_scan"

    override fun onCreate() {
        super.onCreate()
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(channelId, getString(R.string.notification_channel), NotificationManager.IMPORTANCE_DEFAULT))
        startForeground(920, notification("Analista está preparando el universo dinámico"))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        scope.launch {
            DiagnosticsStore.markStart(this@ScanService)
            val app = application as AnalistaApplication
            val result = runCatching {
                val universe = app.dynamicScanCoordinator.prepare()
                val run = app.repository.runScan()
                run to universe
            }
            val text = result.fold(
                onSuccess = { (run, universe) ->
                    "Scan ${run.trustStatus}: ${run.candidateCount}/${universe.symbols.size} · ${universe.status}"
                },
                onFailure = { "Scan fallido: ${it.message ?: "error desconocido"}" }
            )
            DiagnosticsStore.markFinish(
                this@ScanService,
                result.fold(onSuccess = { it.first.status }, onFailure = { "FAILED" })
            )
            getSystemService(NotificationManager::class.java).notify(921, notification(text))
            ScanScheduler.scheduleNext(this@ScanService)
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf(startId)
        }
        return START_NOT_STICKY
    }

    private fun notification(text: String) = NotificationCompat.Builder(this, channelId)
        .setSmallIcon(android.R.drawable.ic_popup_sync)
        .setContentTitle("Analista")
        .setContentText(text)
        .setOngoing(text.contains("preparando"))
        .build()

    override fun onBind(intent: Intent?): IBinder? = null
}
