package com.communionafterdark.cad.ui.viewmodel

import android.content.ComponentName
import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.communionafterdark.cad.data.CadRepository
import com.communionafterdark.cad.data.api.ApiClient
import com.communionafterdark.cad.data.model.Episode
import com.communionafterdark.cad.data.model.Track
import com.communionafterdark.cad.player.CadPlayerService
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
                controller = future.get()
                startPositionPolling()
            },
            ContextCompat.getMainExecutor(context),
        )
    }

    private fun startPositionPolling() {
        viewModelScope.launch {
            while (true) {
                delay(500)
                val ctrl = controller ?: continue
                val posMs = ctrl.currentPosition
                val durMs = ctrl.duration.coerceAtLeast(0L)
                val playing = ctrl.isPlaying
                val posSec = posMs / 1000L
                _state.update {
                    it.copy(
                        isPlaying = playing,
                        positionMs = posMs,
                        durationMs = durMs,
                        currentTrackPosition = currentTrackPosition(posSec),
                    )
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
                    .setArtworkUri(
                        android.net.Uri.parse(episode.artworkUrl(ApiClient.BASE_URL))
                    )
                    .build()
            )
            .build()

        controller?.let { ctrl ->
            ctrl.setMediaItem(mediaItem)
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
