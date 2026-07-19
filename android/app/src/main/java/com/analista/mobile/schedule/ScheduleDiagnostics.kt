package com.analista.mobile.schedule

import android.Manifest
import android.app.AlarmManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat

data class ScheduleDiagnostics(
    val notificationsGranted: Boolean,
    val exactAlarmGranted: Boolean,
    val nextTriggerMillis: Long,
    val lastAutomaticStartMillis: Long,
    val lastAutomaticFinishMillis: Long,
    val lastAutomaticStatus: String
)

object DiagnosticsStore {
    private const val PREFS = "scheduler"

    fun snapshot(context: Context): ScheduleDiagnostics {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val notifications = Build.VERSION.SDK_INT < 33 ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
        val alarmManager = context.getSystemService(AlarmManager::class.java)
        val exact = Build.VERSION.SDK_INT < Build.VERSION_CODES.S || alarmManager.canScheduleExactAlarms()
        return ScheduleDiagnostics(
            notificationsGranted = notifications,
            exactAlarmGranted = exact,
            nextTriggerMillis = prefs.getLong("next_trigger", 0L),
            lastAutomaticStartMillis = prefs.getLong("last_auto_start", 0L),
            lastAutomaticFinishMillis = prefs.getLong("last_auto_finish", 0L),
            lastAutomaticStatus = prefs.getString("last_auto_status", "Aún no ejecutada") ?: "Aún no ejecutada"
        )
    }

    fun markStart(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putLong("last_auto_start", System.currentTimeMillis())
            .putString("last_auto_status", "RUNNING").apply()
    }

    fun markFinish(context: Context, status: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putLong("last_auto_finish", System.currentTimeMillis())
            .putString("last_auto_status", status).apply()
    }
}
