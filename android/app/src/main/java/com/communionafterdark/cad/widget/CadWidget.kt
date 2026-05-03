package com.communionafterdark.cad.widget

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.datastore.preferences.core.Preferences
import androidx.glance.GlanceId
import androidx.glance.GlanceModifier
import androidx.glance.Image
import androidx.glance.ImageProvider
import androidx.glance.action.ActionParameters
import androidx.glance.action.clickable
import androidx.glance.appwidget.GlanceAppWidget
import androidx.glance.appwidget.GlanceAppWidgetManager
import androidx.glance.appwidget.action.ActionCallback
import androidx.glance.appwidget.action.actionRunCallback
import androidx.glance.appwidget.action.actionStartActivity
import androidx.glance.appwidget.provideContent
import androidx.glance.appwidget.state.updateAppWidgetState
import androidx.glance.background
import androidx.glance.currentState
import androidx.glance.layout.Alignment
import androidx.glance.layout.Column
import androidx.glance.layout.ContentScale
import androidx.glance.layout.Row
import androidx.glance.layout.Spacer
import androidx.glance.layout.fillMaxHeight
import androidx.glance.layout.fillMaxSize
import androidx.glance.layout.padding
import androidx.glance.layout.size
import androidx.glance.layout.width
import androidx.glance.state.PreferencesGlanceStateDefinition
import androidx.glance.text.FontWeight
import androidx.glance.text.Text
import androidx.glance.text.TextStyle
import androidx.glance.color.ColorProvider
import com.communionafterdark.cad.MainActivity
import com.communionafterdark.cad.R
import com.communionafterdark.cad.data.CadRepository
import com.communionafterdark.cad.data.api.ApiClient
import com.communionafterdark.cad.player.CadPlayerService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

internal fun parseTimestampMs(ts: String): Long {
    return try {
        val parts = ts.trim().split(":").map { it.toLong() }
        when (parts.size) {
            2 -> (parts[0] * 60 + parts[1]) * 1000L
            3 -> (parts[0] * 3600 + parts[1] * 60 + parts[2]) * 1000L
            else -> 0L
        }
    } catch (_: NumberFormatException) {
        0L
    }
}

class PlayPauseAction : ActionCallback {
    override suspend fun onAction(context: Context, glanceId: GlanceId, parameters: ActionParameters) {
        ContextCompat.startForegroundService(
            context,
            Intent(context, CadPlayerService::class.java).apply {
                action = CadPlayerService.ACTION_PLAY_PAUSE
            }
        )
    }
}

class RandomAction : ActionCallback {
    override suspend fun onAction(context: Context, glanceId: GlanceId, parameters: ActionParameters) {
        val repo = CadRepository()
        val episodes = withContext(Dispatchers.IO) {
            repo.getEpisodes(audioOnly = true, limit = 1000).getOrNull()?.ifEmpty { null }
        } ?: return
        val episode = episodes.random()
        val tracks = withContext(Dispatchers.IO) {
            repo.getTracks(episode.id).getOrNull()?.ifEmpty { null }
        } ?: return
        val track = tracks.random()

        ContextCompat.startForegroundService(
            context,
            Intent(context, CadPlayerService::class.java).apply {
                action = CadPlayerService.ACTION_PLAY_URI
                putExtra(CadPlayerService.EXTRA_URI, episode.audioUrl(ApiClient.BASE_URL))
                putExtra(CadPlayerService.EXTRA_TITLE, episode.displayTitle)
                putExtra(CadPlayerService.EXTRA_EPISODE_ID, episode.id)
                putExtra(CadPlayerService.EXTRA_POSITION_MS, parseTimestampMs(track.timestamp))
                if (episode.hasArtwork) {
                    putExtra(CadPlayerService.EXTRA_ARTWORK_URI, episode.artworkUrl(ApiClient.BASE_URL))
                }
            }
        )
    }
}

class CadWidget : GlanceAppWidget() {

    override val stateDefinition = PreferencesGlanceStateDefinition

    override suspend fun provideGlance(context: Context, id: GlanceId) {
        provideContent {
            val prefs = currentState<Preferences>()
            val title = prefs[CadWidgetKeys.titleKey] ?: ""
            val trackName = prefs[CadWidgetKeys.trackNameKey] ?: ""
            val isPlaying = prefs[CadWidgetKeys.isPlayingKey] ?: false
            val artworkPath = prefs[CadWidgetKeys.artworkPathKey] ?: ""
            val episodeId = prefs[CadWidgetKeys.episodeIdKey] ?: -1

            val openIntent = Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            val openAction = actionStartActivity(openIntent)

            Row(
                modifier = GlanceModifier
                    .fillMaxSize()
                    .background(Color(0xFF000000))
                    .padding(8.dp),
                verticalAlignment = Alignment.Vertical.CenterVertically,
            ) {
                val artworkBitmap = getArtworkBitmap(artworkPath, episodeId)

                if (artworkBitmap != null) {
                    Image(
                        provider = ImageProvider(artworkBitmap),
                        contentDescription = title,
                        contentScale = ContentScale.Crop,
                        modifier = GlanceModifier.size(56.dp).clickable(openAction),
                    )
                } else {
                    Image(
                        provider = ImageProvider(R.mipmap.ic_launcher),
                        contentDescription = null,
                        modifier = GlanceModifier.size(56.dp).clickable(openAction),
                    )
                }

                Spacer(GlanceModifier.width(8.dp))

                Column(
                    modifier = GlanceModifier
                        .defaultWeight()
                        .fillMaxHeight()
                        .clickable(openAction),
                    verticalAlignment = Alignment.Vertical.CenterVertically,
                ) {
                    Text(
                        text = if (episodeId != -1) title else "Tap shuffle to play",
                        style = TextStyle(
                            color = ColorProvider(day = Color(0xFFFFFFFF), night = Color(0xFFFFFFFF)),
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                        ),
                        maxLines = 1,
                    )
                    if (trackName.isNotEmpty()) {
                        Text(
                            text = trackName,
                            style = TextStyle(
                                color = ColorProvider(day = Color(0xFFABABAB), night = Color(0xFFABABAB)),
                                fontSize = 11.sp,
                            ),
                            maxLines = 1,
                        )
                    }
                }

                Spacer(GlanceModifier.width(4.dp))

                Image(
                    provider = ImageProvider(
                        if (isPlaying) R.drawable.ic_widget_pause else R.drawable.ic_widget_play
                    ),
                    contentDescription = if (isPlaying) "Pause" else "Play",
                    modifier = GlanceModifier.size(40.dp).clickable(actionRunCallback<PlayPauseAction>()),
                )

                Image(
                    provider = ImageProvider(R.drawable.ic_widget_shuffle),
                    contentDescription = "Random",
                    modifier = GlanceModifier.size(40.dp).clickable(actionRunCallback<RandomAction>()),
                )
            }
        }
    }

    companion object {
        @Volatile private var cachedArtworkEpisodeId: Int = -1
        @Volatile private var cachedArtworkBitmap: Bitmap? = null

        private fun getArtworkBitmap(path: String, episodeId: Int): Bitmap? {
            if (path.isEmpty() || episodeId == -1) return null
            if (episodeId == cachedArtworkEpisodeId) return cachedArtworkBitmap
            val bitmap = runCatching { BitmapFactory.decodeFile(path) }.getOrNull()
            cachedArtworkEpisodeId = episodeId
            cachedArtworkBitmap = bitmap
            return bitmap
        }

        suspend fun updateState(
            context: Context,
            title: String? = null,
            trackName: String? = null,
            isPlaying: Boolean? = null,
            artworkPath: String? = null,
            episodeId: Int? = null,
        ) {
            val glanceIds = GlanceAppWidgetManager(context).getGlanceIds(CadWidget::class.java)
            if (glanceIds.isEmpty()) return
            val widget = CadWidget()
            glanceIds.forEach { id ->
                updateAppWidgetState(context, PreferencesGlanceStateDefinition, id) { prefs ->
                    prefs.toMutablePreferences().apply {
                        title?.let { this[CadWidgetKeys.titleKey] = it }
                        trackName?.let { this[CadWidgetKeys.trackNameKey] = it }
                        isPlaying?.let { this[CadWidgetKeys.isPlayingKey] = it }
                        artworkPath?.let { this[CadWidgetKeys.artworkPathKey] = it }
                        episodeId?.let { this[CadWidgetKeys.episodeIdKey] = it }
                    }
                }
                widget.update(context, id)
            }
        }
    }
}
