package com.communionafterdark.cad.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.communionafterdark.cad.data.api.ApiClient
import com.communionafterdark.cad.ui.components.TrackRow
import com.communionafterdark.cad.ui.theme.AccentRed
import com.communionafterdark.cad.ui.theme.Black
import com.communionafterdark.cad.ui.theme.Border
import com.communionafterdark.cad.ui.theme.TextSecondary
import com.communionafterdark.cad.ui.theme.White
import com.communionafterdark.cad.ui.viewmodel.EpisodeDetailViewModel
import com.communionafterdark.cad.ui.viewmodel.PlayerViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EpisodeDetailScreen(
    episodeId: Int,
    detailVm: EpisodeDetailViewModel,
    playerVm: PlayerViewModel,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val uiState by detailVm.uiState.collectAsState()
    val playerState by playerVm.state.collectAsState()
    val listState = rememberLazyListState()

    LaunchedEffect(episodeId) {
        detailVm.loadEpisode(episodeId)
    }

    // Scroll to the active track whenever it changes or tracks finish loading.
    // Item layout: 0 = artwork, 1 = metadata, 2 = tracklist header, 3+ = track rows.
    val activeTrackIndex = uiState.tracks.indexOfFirst { it.position == playerState.currentTrackPosition }
    LaunchedEffect(playerState.currentTrackPosition, uiState.tracks.size) {
        if (activeTrackIndex >= 0 && uiState.tracks.isNotEmpty()) {
            listState.animateScrollToItem(activeTrackIndex + 3)
        }
    }

    Column(modifier = modifier) {
        // Top app bar
        TopAppBar(
            title = {
                Text(
                    text = uiState.episode?.displayTitle ?: "",
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    color = White,
                )
            },
            navigationIcon = {
                IconButton(onClick = onBack) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = "Back",
                        tint = White,
                    )
                }
            },
            colors = TopAppBarDefaults.topAppBarColors(
                containerColor = Black,
                titleContentColor = White,
            ),
        )

        if (uiState.isLoading) {
            CircularProgressIndicator(modifier = Modifier.padding(16.dp))
            return@Column
        }

        val episode = uiState.episode ?: run {
            Text(
                text = uiState.error ?: "Episode not found",
                color = TextSecondary,
                modifier = Modifier.padding(16.dp),
            )
            return@Column
        }

        LazyColumn(state = listState) {
            // Item 0: full-width artwork
            item {
                AsyncImage(
                    model = episode.artworkUrl(ApiClient.BASE_URL),
                    contentDescription = episode.displayTitle,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .fillMaxWidth()
                        .aspectRatio(1f),
                )
            }

            // Item 1: metadata + description + play button
            item {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = episode.displayTitle,
                        style = androidx.compose.material3.MaterialTheme.typography.headlineLarge,
                        color = White,
                    )

                    Spacer(modifier = Modifier.height(4.dp))

                    Text(
                        text = episode.pubDate ?: "",
                        color = TextSecondary,
                        fontSize = 14.sp,
                    )

                    Spacer(modifier = Modifier.height(16.dp))

                    Button(
                        onClick = { playerVm.playEpisode(episode, uiState.tracks) },
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(containerColor = AccentRed),
                    ) {
                        Text(
                            text = "PLAY EPISODE",
                            color = White,
                            fontWeight = FontWeight.Bold,
                        )
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    HorizontalDivider(color = Border)

                    if (!episode.description.isNullOrBlank()) {
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(
                            text = episode.description,
                            color = TextSecondary,
                            fontSize = 14.sp,
                        )
                    }
                }
            }

            if (uiState.tracks.isNotEmpty()) {
                // Item 2: tracklist header
                item {
                    Text(
                        text = "TRACKLIST",
                        color = AccentRed,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 0.1.sp,
                        modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 8.dp),
                    )
                }

                // Items 3+: individual track rows
                items(uiState.tracks) { track ->
                    TrackRow(
                        track = track,
                        isActive = playerState.currentTrackPosition == track.position &&
                                playerState.episode?.id == uiState.episode?.id,
                        isFavorite = track.position in uiState.favoritedPositions,
                        onSeek = {
                            val episode = uiState.episode ?: return@TrackRow
                            if (playerState.episode?.id == episode.id) {
                                playerVm.seekToTimestamp(track.timestamp)
                            } else {
                                playerVm.playEpisodeFromTimestamp(episode, uiState.tracks, track.timestamp)
                            }
                        },
                        onToggleFavorite = { detailVm.toggleFavorite(episodeId, track.position) },
                    )
                    HorizontalDivider(color = Border, thickness = 0.5.dp)
                }
            }
        }
    }
}
