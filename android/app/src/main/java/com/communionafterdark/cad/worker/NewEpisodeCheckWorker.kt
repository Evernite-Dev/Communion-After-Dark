package com.communionafterdark.cad.worker

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.PackageManager
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.core.content.edit
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.communionafterdark.cad.R
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class NewEpisodeCheckWorker(
    ctx: Context,
    params: WorkerParameters,
) : CoroutineWorker(ctx, params) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val prefs = applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val lastCheck = prefs.getLong(KEY_LAST_CHECK, 0L)
        val since = if (lastCheck > 0L) lastCheck else (System.currentTimeMillis() / 1000 - 86400)

        val url = "$POLL_URL/json?poll=1&since=$since"
        val response = try {
            OkHttpClient().newCall(Request.Builder().url(url).build()).execute()
        } catch (_: Exception) {
            return@withContext Result.retry()
        }

        val body = response.body?.string()
        response.close()

        if (!body.isNullOrBlank()) {
            val lastLine = body.lines().lastOrNull { it.isNotBlank() }
            if (lastLine != null) {
                val message = try {
                    JSONObject(lastLine).optString("message", "New episode available")
                } catch (_: Exception) {
                    "New episode available"
                }
                showNotification(applicationContext, message)
            }
        }

        prefs.edit { putLong(KEY_LAST_CHECK, System.currentTimeMillis() / 1000) }
        Result.success()
    }

    private fun showNotification(ctx: Context, message: String) {
        if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS)
            != PackageManager.PERMISSION_GRANTED) return
        val notif = NotificationCompat.Builder(ctx, CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher_foreground)
            .setContentTitle("Communion After Dark")
            .setContentText(message)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setAutoCancel(true)
            .build()
        NotificationManagerCompat.from(ctx).notify(NOTIF_ID, notif)
    }

    companion object {
        // Update this to your Synology reverse proxy hostname
        const val POLL_URL = "http://192.168.1.30:8090/cad-new-episode"

        private const val CHANNEL_ID = "cad_new_episode"
        private const val CHANNEL_NAME = "New Episode"
        private const val NOTIF_ID = 1001
        private const val WORK_NAME = "cad_episode_check"
        private const val PREFS_NAME = "cad_notif"
        private const val KEY_LAST_CHECK = "last_check"

        fun createNotificationChannel(ctx: Context) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_DEFAULT,
            ).apply {
                description = "Notifies when a new Communion After Dark episode is available"
            }
            ctx.getSystemService(NotificationManager::class.java)
                .createNotificationChannel(channel)
        }

        fun scheduleIfNeeded(ctx: Context) {
            val request = PeriodicWorkRequestBuilder<NewEpisodeCheckWorker>(1, TimeUnit.HOURS)
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build()
                )
                .build()
            WorkManager.getInstance(ctx).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request,
            )
        }
    }
}
