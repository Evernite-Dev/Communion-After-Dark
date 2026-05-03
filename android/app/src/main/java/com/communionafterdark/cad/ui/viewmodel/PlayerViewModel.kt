package com.communionafterdark.cad.ui.viewmodel

import android.content.ComponentName
import android.content.Context
import android.os.Bundle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.communionafterdark.cad.data.CadRepository
import com.communionafterdark.cad.data.api.ApiClient
import com.communionafterdark.cad.data.model.Episode
import com.communionafterdark.cad.data.model.Track
import com.communionafterdark.cad.player.CadPlayerService
import com.communionafterdark.cad.widget.CadWidget
import com.google.common.util.concurrent.ListenableFuture
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import androidx.core.content.ContextCompat

data class PlaybackState(
    val episode: Episode? = null,
    val tracks: List<Track> = emptyList(),
    val favoritedPositions: Set<Int> = emptySet(),
    val isPlaying: Boolean = false,
    val positionMs: Long = 0L,
    val durationMs: Long = 0L,
    val currentTrackPosition: Int = -1,
)

class PlayerViewModel(context: Context) : ViewModel() {

    private val appContext: Context = context.applicationContext

    private val _state = MutableStateFlow(PlaybackState())
    val state: StateFlow<PlaybackState> = _state.asStateFlow()

    private val repository = CadRepository()

    private var controller: MediaController? = null
    private var controllerFuture: ListenableFuture<MediaController>? = null

    init {
        val sessionToken = SessionToken(
            context,
            ComponentName(context, CadPlayerService::class.java),
        )
        val future = MediaController.Builder(context, sessionToken).buildAsync()
        controllerFuture = future
        future.addListener(
            {
                try {
                    controller = future.get()
                    startPositionPolling()
                } catch (e: Exception) {
                    // Service connection failed; playback unavailable until next launch
                }
            },
            ContextCompat.getMainExecutor(context),
        )
    }

    private fun syncEpisodeFromMediaItem(mediaItem: MediaItem?) {
        if (mediaItem == null) return
        val episodeId = mediaItem.mediaMetadata.extras?.getInt("episodeId", -1) ?: -1
        if (episodeId == -1) return
        if (episodeId == _state.value.episode?.id) return
        viewModelScope.launch {
            val episode = repository.getEpisode(episodeId).getOrNull() ?: return@launch
            val tracks = repository.getTracks(episodeId).getOrNull() ?: emptyList()
            _state.update { it.copy(episode = episode, tracks = tracks, favoritedPositions = emptySet()) }
        }
    }

    private fun startPositionPolling() {
        val ctrl = controller ?: return

        ctrl.addListener(object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                _state.update { it.copy(isPlaying = isPlaying) }
            }

            override fun onPlaybackStateChanged(playbackState: Int) {
                val durMs = ctrl.duration.coerceAtLeast(0L)
                _state.update { it.copy(durationMs = durMs) }
            }

            override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
                syncEpisodeFromMediaItem(mediaItem)
            }
        })

        // Restore state if service was already playing when the controller connected
        syncEpisodeFromMediaItem(ctrl.currentMediaItem)

        viewModelScope.launch {
            var lastWidgetTrackPosition = Int.MIN_VALUE
            while (true) {
                delay(500)
                if (ctrl.isPlaying) {
                    val posMs = ctrl.currentPosition
                    val posSec = posMs / 1000L
                    val newTrackPos = currentTrackPosition(posSec)
                    _state.update {
                        it.copy(
                            positionMs = posMs,
                            durationMs = ctrl.duration.coerceAtLeast(0L),
                            currentTrackPosition = newTrackPos,
                        )
                    }
                    if (newTrackPos != lastWidgetTrackPosition) {
                        lastWidgetTrackPosition = newTrackPos
                        val trackName = _state.value.tracks
                            .firstOrNull { it.position == newTrackPos }
                            ?.let { "${it.artist} – ${it.title}" } ?: ""
                        CadWidget.updateState(appContext, trackName = trackName)
                    }
                }
            }
        }
    }

    fun playEpisode(episode: Episode, tracks: List<Track>) {
        _state.update { it.copy(episode = episode, tracks = tracks, favoritedPositions = emptySet()) }

        val audioUrl = episode.audioUrl(ApiClient.BASE_URL)
        val mediaItem = MediaItem.Builder()
            .setUri(audioUrl)
            .setMediaMetadata(
                MediaMetadata.Builder()
                    .setTitle(episode.displayTitle)
                    .setExtras(Bundle().apply { putInt("episodeId", episode.id) })
                    .apply {
                        if (episode.hasArtwork) {
                            setArtworkUri(android.net.Uri.parse(episode.artworkUrl(ApiClient.BASE_URL)))
                        }
                    }
                    .build()
            )
            .build()

        controller?.let { ctrl ->
            ctrl.setMediaItem(mediaItem)
            ctrl.prepare()
            ctrl.play()
        }
    }

    fun playEpisodeFromTimestamp(episode: Episode, tracks: List<Track>, timestamp: String) {
        _state.update { it.copy(episode = episode, tracks = tracks, favoritedPositions = emptySet()) }
        val positionMs = parseTimestamp(timestamp)
        val audioUrl = episode.audioUrl(ApiClient.BASE_URL)
        val mediaItem = MediaItem.Builder()
            .setUri(audioUrl)
            .setMediaMetadata(
                MediaMetadata.Builder()
                    .setTitle(episode.displayTitle)
                    .setExtras(Bundle().apply { putInt("episodeId", episode.id) })
                    .apply {
                        if (episode.hasArtwork) {
                            setArtworkUri(android.net.Uri.parse(episode.artworkUrl(ApiClient.BASE_URL)))
                        }
                    }
                    .build()
            )
            .build()

        controller?.let { ctrl ->
            ctrl.setMediaItem(mediaItem)
            ctrl.seekTo(positionMs)
            ctrl.prepare()
            ctrl.play()
        }
    }

    fun togglePlayPause() {
        val ctrl = controller ?: return
        if (ctrl.isPlaying) {
            ctrl.pause()
        } else {
            ctrl.play()
        }
    }

    fun seekTo(positionMs: Long) {
        controller?.seekTo(positionMs)
    }

    fun seekToTimestamp(timestamp: String) {
        val ms = parseTimestamp(timestamp)
        seekTo(ms)
    }

    fun toggleFavorite(episodeId: Int, position: Int) {
        _state.update {
            val newFavs = if (position in it.favoritedPositions) {
                it.favoritedPositions - position
            } else {
                it.favoritedPositions + position
            }
            it.copy(favoritedPositions = newFavs)
        }
        viewModelScope.launch {
            repository.toggleFavorite(episodeId, position)
        }
    }

    private fun currentTrackPosition(posSec: Long): Int {
        if (_state.value.tracks.isEmpty()) return -1
        var result = -1
        for (track in _state.value.tracks) {
            val trackSec = parseTimestampToSec(track.timestamp)
            if (trackSec <= posSec) {
                result = track.position
            } else {
                break
            }
        }
        return result
    }

    private fun parseTimestamp(ts: String): Long {
        return parseTimestampToSec(ts) * 1000L
    }

    private fun parseTimestampToSec(ts: String): Long {
        return try {
            val parts = ts.trim().split(":").map { it.toLong() }
            when (parts.size) {
                2 -> parts[0] * 60 + parts[1]
                3 -> parts[0] * 3600 + parts[1] * 60 + parts[2]
                else -> 0L
            }
        } catch (e: NumberFormatException) {
            0L
        }
    }

    private var lastPrevPressMs = 0L

    fun prevTrack() {
        val tracks = _state.value.tracks
        val ctrl = controller ?: return
        val currentIdx = tracks.indexOfFirst { it.position == _state.value.currentTrackPosition }
        val now = System.currentTimeMillis()
        val isDoublePress = lastPrevPressMs != 0L && (now - lastPrevPressMs) < 3000L
        lastPrevPressMs = now
        if (isDoublePress && currentIdx > 0) {
            ctrl.seekTo(parseTimestamp(tracks[currentIdx - 1].timestamp))
        } else {
            val currentTrackMs = if (currentIdx >= 0) parseTimestamp(tracks[currentIdx].timestamp) else 0L
            ctrl.seekTo(currentTrackMs)
        }
    }

    fun nextTrack() {
        val tracks = _state.value.tracks
        val ctrl = controller ?: return
        val currentIdx = tracks.indexOfFirst { it.position == _state.value.currentTrackPosition }
        if (currentIdx >= 0 && currentIdx < tracks.size - 1) {
            ctrl.seekTo(parseTimestamp(tracks[currentIdx + 1].timestamp))
        }
    }

    override fun onCleared() {
        controllerFuture?.let { MediaController.releaseFuture(it) }
        controller = null
        super.onCleared()
    }

    class Factory(private val context: Context) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            if (modelClass.isAssignableFrom(PlayerViewModel::class.java)) {
                return PlayerViewModel(context.applicationContext) as T
            }
            throw IllegalArgumentException("Unknown ViewModel class: ${modelClass.name}")
        }
    }
}
