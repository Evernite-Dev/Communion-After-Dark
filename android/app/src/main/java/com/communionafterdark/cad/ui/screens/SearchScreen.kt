package com.communionafterdark.cad.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.outlined.FavoriteBorder
import androidx.compose.material3.IconButton
import com.communionafterdark.cad.ui.theme.AccentRed
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.communionafterdark.cad.ui.theme.AccentRed
import com.communionafterdark.cad.ui.theme.Border
import com.communionafterdark.cad.ui.theme.Surface
import com.communionafterdark.cad.ui.theme.TextDim
import com.communionafterdark.cad.ui.theme.TextSecondary
import com.communionafterdark.cad.ui.theme.White
import com.communionafterdark.cad.ui.viewmodel.SearchViewModel

@Composable
fun SearchScreen(
    searchVm: SearchViewModel,
    onEpisodeClick: (Int) -> Unit,
    onTrackPlay: (episodeId: Int, timestamp: String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val uiState by searchVm.uiState.collectAsState()

    Column(modifier = modifier.fillMaxSize()) {
        // Search input
        OutlinedTextField(
            value = uiState.query,
            onValueChange = { searchVm.search(it) },
            placeholder = {
                Text(
                    text = "Search tracks, artists, albums\u2026",
                    color = TextDim,
                )
            },
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = AccentRed,
                unfocusedBorderColor = Border,
                cursorColor = AccentRed,
                focusedContainerColor = Surface,
                unfocusedContainerColor = Surface,
                focusedTextColor = White,
                unfocusedTextColor = White,
            ),
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            singleLine = true,
        )

        HorizontalDivider(color = Border)

        when {
            uiState.isLoading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }
            uiState.query.length < 2 -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(
                        text = "Search tracks, artists, albums\u2026",
                        color = TextDim,
                    )
                }
            }
            uiState.results.isEmpty() && uiState.query.length >= 2 -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(
                        text = "No results for \"${uiState.query}\"",
                        color = TextDim,
                    )
                }
            }
            else -> {
                LazyColumn(modifier = Modifier.fillMaxSize()) {
                    items(uiState.results, key = { it.id }) { result ->
                        val isFavorite = "${result.episodeId}_${result.position}" in uiState.favoritedKeys
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { onTrackPlay(result.episodeId, result.timestamp) }
                                .padding(start = 12.dp, top = 8.dp, bottom = 8.dp, end = 4.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            // Artwork thumbnail
                            if (result.artworkPath != null) {
                                AsyncImage(
                                    model = result.artworkUrl(com.communionafterdark.cad.data.api.ApiClient.BASE_URL),
                                    contentDescription = result.episodeTitle,
                                    contentScale = ContentScale.Crop,
                                    modifier = Modifier.size(56.dp),
                                )
                            } else {
                                Box(
                                    modifier = Modifier.size(56.dp),
                                    contentAlignment = Alignment.Center,
                                ) {
                                    Icon(
                                        imageVector = Icons.Filled.MusicNote,
                                        contentDescription = null,
                                        tint = TextDim,
                                        modifier = Modifier.size(32.dp),
                                    )
                                }
                            }

                            Spacer(modifier = Modifier.width(12.dp))

                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = "${result.artist} \u2014 ${result.title}",
                                    color = White,
                                    fontSize = 14.sp,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                                Text(
                                    text = "${result.episodeTitle ?: "Unknown episode"} · ${result.timestamp}",
                                    color = TextSecondary,
                                    fontSize = 12.sp,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                            }

                            IconButton(onClick = { searchVm.toggleFavorite(result.episodeId, result.position) }) {
                                Icon(
                                    imageVector = if (isFavorite) Icons.Filled.Favorite else Icons.Outlined.FavoriteBorder,
                                    contentDescription = if (isFavorite) "Remove from favorites" else "Add to favorites",
                                    tint = if (isFavorite) AccentRed else TextDim,
                                )
                            }
                            Icon(
                                imageVector = Icons.Filled.PlayArrow,
                                contentDescription = "Play",
                                tint = TextDim,
                                modifier = Modifier.padding(end = 8.dp),
                            )
                        }
                        HorizontalDivider(color = Border, thickness = 0.5.dp)
                    }
                }
            }
        }
    }
}
