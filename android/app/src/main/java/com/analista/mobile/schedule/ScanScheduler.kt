package com.analista.mobile.schedule

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.provider.Settings
import com.analista.mobile.domain.NyseCalendar

object ScanScheduler {
    fun canScheduleExact(context: Context): Boolean { val manager = context.getSystemService(AlarmManager::class.java); return Build.VERSION.SDK_INT < Build.VERSION_CODES.S || manager.canScheduleExactAlarms() }
    fun permissionIntent(context: Context): Intent = Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM).apply { data = android.net.Uri.parse("package:${context.packageName}") }
    fun scheduleNext(context: Context): Long {
        val manager = context.getSystemService(AlarmManager::class.java); val trigger = NyseCalendar.nextScheduled().toInstant().toEpochMilli()
        val pending = PendingIntent.getBroadcast(context, 920, Intent(context, ScanAlarmReceiver::class.java), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        if (canScheduleExact(context)) manager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, trigger, pending) else manager.setWindow(AlarmManager.RTC_WAKEUP, trigger, 10 * 60 * 1000L, pending)
        context.getSharedPreferences("scheduler", Context.MODE_PRIVATE).edit().putLong("next_trigger", trigger).apply(); return trigger
    }
    fun nextTrigger(context: Context): Long = context.getSharedPreferences("scheduler", Context.MODE_PRIVATE).getLong("next_trigger", 0L)
}
