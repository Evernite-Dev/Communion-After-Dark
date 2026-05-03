package com.communionafterdark.cad.player

import android.app.PendingIntent
import android.content.Intent
import android.net.Uri
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService
import com.communionafterdark.cad.MainActivity
import com.communionafterdark.cad.data.api.ApiClient
import com.communionafterdark.cad.widget.CadWidget
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

class CadPlayerService : MediaSessionService() {

    private var mediaSession: MediaSession? = null
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    private val widgetPlayerListener = object : Player.Listener {
        override fun onIsPlayingChanged(isPlaying: Boolean) {
            serviceScope.launch {
                CadWidget.updateState(applicationContext, isPlaying = isPlaying)
            }
        }

        override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
            val episodeId = mediaItem?.mediaMetadata?.extras?.getInt("episodeId", -1) ?: -1
            val title = mediaItem?.mediaMetadata?.title?.toString() ?: ""
            serviceScope.launch {
                val artworkFile = if (episodeId != -1) downloadArtwork(episodeId) else null
                CadWidget.updateState(
                    applicationContext,
                    title = title,
                    trackName = "",
                    episodeId = episodeId,
                    artworkPath = artworkFile?.absolutePath ?: "",
                )
            }
        }
    }

    override fun onCreate() {
        super.onCreate()

        val audioAttributes = AudioAttributes.Builder()
            .setUsage(C.USAGE_MEDIA)
            .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC)
            .build()

        val player = ExoPlayer.Builder(this)
            .setAudioAttributes(audioAttributes, /* handleAudioFocus= */ true)
            .build()

        player.addListener(widgetPlayerListener)

        val sessionActivity = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )

        mediaSession = MediaSession.Builder(this, player)
            .setSessionActivity(sessionActivity)
            .build()
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaSession? {
        return mediaSession
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val player = mediaSession?.player
        when (intent?.action) {
            ACTION_PLAY_PAUSE -> {
                if (player != null) {
                    if (player.isPlaying) player.pause()
                    else if (player.currentMediaItem != null) player.play()
                }
            }
            ACTION_PLAY_URI -> {
                val uriString = intent.getStringExtra(EXTRA_URI)
                if (player != null && uriString != null) {
                    val title = intent.getStringExtra(EXTRA_TITLE) ?: ""
                    val episodeId = intent.getIntExtra(EXTRA_EPISODE_ID, -1)
                    val positionMs = intent.getLongExtra(EXTRA_POSITION_MS, 0L)
                    val artworkUriString = intent.getStringExtra(EXTRA_ARTWORK_URI)
                    val mediaItem = MediaItem.Builder()
                        .setUri(uriString)
                        .setMediaMetadata(
                            androidx.media3.common.MediaMetadata.Builder()
                                .setTitle(title)
                                .setExtras(android.os.Bundle().apply { putInt("episodeId", episodeId) })
                                .apply {
                                    if (artworkUriString != null) {
                                        setArtworkUri(Uri.parse(artworkUriString))
                                    }
                                }
                                .build()
                        )
                        .build()
                    player.setMediaItem(mediaItem)
                    player.seekTo(positionMs)
                    player.prepare()
                    player.play()
                }
            }
        }
        return super.onStartCommand(intent, flags, startId)
    }

    companion object {
        const val ACTION_PLAY_PAUSE = "com.communionafterdark.cad.ACTION_PLAY_PAUSE"
        const val ACTION_PLAY_URI = "com.communionafterdark.cad.ACTION_PLAY_URI"
        const val EXTRA_URI = "uri"
        const val EXTRA_TITLE = "title"
        const val EXTRA_EPISODE_ID = "episodeId"
        const val EXTRA_POSITION_MS = "positionMs"
        const val EXTRA_ARTWORK_URI = "artworkUri"
    }

    override fun onTaskRemoved(rootIntent: android.content.Intent?) {
        val player = mediaSession?.player
        if (player == null || !player.playWhenReady) {
            stopSelf()
        }
    }

    override fun onDestroy() {
        serviceScope.cancel()
        mediaSession?.run {
            player.removeListener(widgetPlayerListener)
            player.release()
            release()
        }
        mediaSession = null
        super.onDestroy()
    }

    private suspend fun downloadArtwork(episodeId: Int): File? = withContext(Dispatchers.IO) {
        try {
            val artworkFile = File(filesDir, "widget_artwork.jpg")
            val urlString = "${ApiClient.BASE_URL.trimEnd('/')}/api/episodes/$episodeId/artwork"
            java.net.URL(urlString).openStream().use { input ->
                artworkFile.outputStream().use { output ->
                    input.copyTo(output)
                }
            }
            artworkFile
        } catch (_: Exception) {
            null
        }
    }
}
