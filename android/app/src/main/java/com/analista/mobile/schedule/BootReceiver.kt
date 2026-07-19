package com.analista.mobile.schedule

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class BootReceiver : BroadcastReceiver() { override fun onReceive(context: Context, intent: Intent?) { ScanScheduler.scheduleNext(context) } }
