package com.communionafterdark.cad.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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

    LaunchedEffect(episodeId) {
        detailVm.loadEpisode(episodeId)
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

        Column(
            modifier = Modifier.verticalScroll(rememberScrollState()),
        ) {
            // Full-width artwork
            AsyncImage(
                model = episode.artworkUrl(ApiClient.BASE_URL),
                contentDescription = episode.displayTitle,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(1f),
            )

            Column(modifier = Modifier.padding(16.dp)) {
                // Title
                Text(
                    text = episode.displayTitle,
                    style = androidx.compose.material3.MaterialTheme.typography.headlineLarge,
                    color = White,
                )

                Spacer(modifier = Modifier.height(4.dp))

                // Date
                Text(
                    text = episode.pubDate ?: "",
                    color = TextSecondary,
                    fontSize = 14.sp,
                )

                Spacer(modifier = Modifier.height(16.dp))

                // Play button
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

                Spacer(modifier = Modifier.height(8.dp))

                // Description
                if (!episode.description.isNullOrBlank()) {
                    Text(
                        text = episode.description,
                        color = TextSecondary,
                        fontSize = 14.sp,
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                }

                // Tracklist header
                if (uiState.tracks.isNotEmpty()) {
                    Text(
                        text = "TRACKLIST",
                        color = AccentRed,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 0.1.sp,
                    )

                    Spacer(modifier = Modifier.height(8.dp))

                    // Track rows
                    uiState.tracks.forEach { track ->
                        TrackRow(
                            track = track,
                            isActive = playerState.currentTrackPosition == track.position,
                            isFavorite = track.position in uiState.favoritedPositions,
                            onSeek = { playerVm.seekToTimestamp(track.timestamp) },
                            onToggleFavorite = { detailVm.toggleFavorite(episodeId, track.position) },
                        )
                        HorizontalDivider(color = Border, thickness = 0.5.dp)
                    }
                }
            }
        }
    }
}
