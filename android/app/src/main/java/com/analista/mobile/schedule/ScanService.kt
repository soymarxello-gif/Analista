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
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO); private val channelId = "analista_scan"
    override fun onCreate() { super.onCreate(); getSystemService(NotificationManager::class.java).createNotificationChannel(NotificationChannel(channelId, getString(R.string.notification_channel), NotificationManager.IMPORTANCE_DEFAULT)); startForeground(920, notification("Analista está ejecutando el scan premarket")) }
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        scope.launch {
            val result = runCatching { (application as AnalistaApplication).repository.runScan() }
            val text = result.fold({ "Scan ${it.trustStatus}: ${it.candidateCount} símbolos analizados" }, { "Scan fallido: ${it.message ?: "error desconocido"}" })
            getSystemService(NotificationManager::class.java).notify(921, notification(text)); ScanScheduler.scheduleNext(this@ScanService); stopForeground(STOP_FOREGROUND_REMOVE); stopSelf(startId)
        }; return START_NOT_STICKY
    }
    private fun notification(text: String) = NotificationCompat.Builder(this, channelId).setSmallIcon(android.R.drawable.ic_popup_sync).setContentTitle("Analista").setContentText(text).setOngoing(text.contains("ejecutando")).build()
    override fun onBind(intent: Intent?): IBinder? = null
}
