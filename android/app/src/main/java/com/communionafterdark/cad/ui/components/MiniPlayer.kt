package com.communionafterdark.cad.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.automirrored.filled.QueueMusic
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.communionafterdark.cad.data.api.ApiClient
import com.communionafterdark.cad.ui.theme.AccentRed
import com.communionafterdark.cad.ui.theme.Black
import com.communionafterdark.cad.ui.theme.Border
import com.communionafterdark.cad.ui.theme.Surface
import com.communionafterdark.cad.ui.theme.TextDim
import com.communionafterdark.cad.ui.theme.TextSecondary
import com.communionafterdark.cad.ui.theme.White
import com.communionafterdark.cad.ui.viewmodel.PlaybackState

private fun formatMs(ms: Long): String {
    val totalSec = ms / 1000L
    val hours = totalSec / 3600
    val minutes = (totalSec % 3600) / 60
    val seconds = totalSec % 60
    return "%d:%02d:%02d".format(hours, minutes, seconds)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MiniPlayer(
    state: PlaybackState,
    onTogglePlay: () -> Unit,
    onPrev: () -> Unit,
    onNext: () -> Unit,
    onSeek: (Float) -> Unit,
    onSeekToTimestamp: (String) -> Unit,
    onToggleFavorite: (position: Int) -> Unit,
    onArtworkClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val episode = state.episode ?: return

    var showTracklist by remember { mutableStateOf(false) }
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = false)

    // Auto-scroll the sheet to the active track when it opens
    val listState = rememberLazyListState()
    LaunchedEffect(showTracklist, state.currentTrackPosition) {
        if (showTracklist && state.currentTrackPosition >= 0 && state.tracks.isNotEmpty()) {
            val index = state.tracks.indexOfFirst { it.position == state.currentTrackPosition }
            if (index >= 0) listState.animateScrollToItem(index)
        }
    }

    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(Black),
    ) {
        HorizontalDivider(color = Border, thickness = 1.dp)

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(72.dp)
                .padding(horizontal = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // Artwork thumbnail — tap to navigate to the episode
            AsyncImage(
                model = episode.artworkUrl(ApiClient.BASE_URL),
                contentDescription = episode.displayTitle,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .size(56.dp)
                    .clickable { onArtworkClick() },
            )

            Spacer(modifier = Modifier.width(8.dp))

            // Title + time
            Column(
                modifier = Modifier.weight(1f),
            ) {
                Text(
                    text = episode.displayTitle,
                    color = White,
                    fontSize = 14.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = "${formatMs(state.positionMs)} / ${formatMs(state.durationMs)}",
                    color = TextDim,
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace,
                )
            }

            // Controls
            IconButton(onClick = onPrev) {
                Icon(
                    imageVector = Icons.Filled.SkipPrevious,
                    contentDescription = "Previous",
                    tint = TextDim,
                )
            }
            IconButton(onClick = onTogglePlay) {
                Icon(
                    imageVector = if (state.isPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                    contentDescription = if (state.isPlaying) "Pause" else "Play",
                    tint = AccentRed,
                    modifier = Modifier.size(32.dp),
                )
            }
            IconButton(onClick = onNext) {
                Icon(
                    imageVector = Icons.Filled.SkipNext,
                    contentDescription = "Next",
                    tint = TextDim,
                )
            }
            IconButton(onClick = { showTracklist = true }) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.QueueMusic,
                    contentDescription = "Tracklist",
                    tint = TextSecondary,
                )
            }
        }

        // Seek bar
        val progress = if (state.durationMs > 0) {
            (state.positionMs.toFloat() / state.durationMs.toFloat()).coerceIn(0f, 1f)
        } else {
            0f
        }
        var isDragging by remember { mutableStateOf(false) }
        var dragValue by remember { mutableStateOf(progress) }
        // Keep dragValue in sync with playback when not dragging
        androidx.compose.runtime.LaunchedEffect(progress) {
            if (!isDragging) dragValue = progress
        }
        Slider(
            value = dragValue,
            onValueChange = { value ->
                isDragging = true
                dragValue = value
            },
            onValueChangeFinished = {
                onSeek(dragValue)
                isDragging = false
            },
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 4.dp),
            colors = SliderDefaults.colors(
                thumbColor = AccentRed,
                activeTrackColor = AccentRed,
                inactiveTrackColor = Border,
            ),
        )
    }

    // Tracklist bottom sheet
    if (showTracklist) {
        ModalBottomSheet(
            onDismissRequest = { showTracklist = false },
            sheetState = sheetState,
            containerColor = Surface,
        ) {
            // Header
            Text(
                text = "TRACKLIST",
                color = AccentRed,
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.1.sp,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            )
            Text(
                text = episode.displayTitle,
                color = TextSecondary,
                fontSize = 13.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.padding(horizontal = 16.dp).padding(bottom = 8.dp),
            )
            HorizontalDivider(color = Border)

            if (state.tracks.isEmpty()) {
                Text(
                    text = "No tracklist available for this episode.",
                    color = TextSecondary,
                    fontSize = 14.sp,
                    modifier = Modifier.padding(16.dp),
                )
            } else {
                LazyColumn(state = listState) {
                    items(state.tracks, key = { it.position }) { track ->
                        TrackRow(
                            track = track,
                            isActive = state.currentTrackPosition == track.position,
                            isFavorite = track.position in state.favoritedPositions,
                            onSeek = { onSeekToTimestamp(track.timestamp) },
                            onToggleFavorite = { onToggleFavorite(track.position) },
                        )
                        HorizontalDivider(color = Border, thickness = 0.5.dp)
                    }
                }
            }
        }
    }
}
