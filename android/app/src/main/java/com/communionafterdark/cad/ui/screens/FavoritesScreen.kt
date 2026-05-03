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
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DragHandle
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material3.IconButton
import com.communionafterdark.cad.ui.theme.AccentRed
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import coil.compose.AsyncImage
import com.communionafterdark.cad.data.api.ApiClient
import com.communionafterdark.cad.ui.theme.Border
import com.communionafterdark.cad.ui.theme.TextDim
import com.communionafterdark.cad.ui.theme.TextSecondary
import com.communionafterdark.cad.ui.theme.White
import com.communionafterdark.cad.ui.viewmodel.FavoritesViewModel
import com.communionafterdark.cad.ui.viewmodel.PlayerViewModel
import sh.calvin.reorderable.ReorderableItem
import sh.calvin.reorderable.rememberReorderableLazyListState

@Composable
fun FavoritesScreen(
    favVm: FavoritesViewModel,
    playerVm: PlayerViewModel,
    onEpisodeClick: (Int) -> Unit,
    onTrackPlay: (episodeId: Int, timestamp: String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val uiState by favVm.uiState.collectAsState()

    // Refresh favorites every time this tab comes into view
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                favVm.refresh()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    when {
        uiState.isLoading -> {
            Box(modifier = modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        }
        uiState.error != null -> {
            Box(modifier = modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(text = uiState.error ?: "Unknown error", color = TextSecondary)
            }
        }
        uiState.favorites.isEmpty() -> {
            Box(modifier = modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(
                    text = "No favorites yet.\nHeart a track to save it here.",
                    color = TextDim,
                )
            }
        }
        else -> {
            val lazyListState = rememberLazyListState()
            val reorderableState = rememberReorderableLazyListState(lazyListState) { from, to ->
                favVm.reorder(from.index, to.index)
            }

            LazyColumn(
                state = lazyListState,
                modifier = modifier.fillMaxSize(),
            ) {
                items(uiState.favorites, key = { it.id }) { favorite ->
                    ReorderableItem(reorderableState, key = favorite.id) { isDragging ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { onTrackPlay(favorite.episodeId, favorite.timestamp) }
                                .padding(horizontal = 12.dp, vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            // Drag handle
                            Icon(
                                imageVector = Icons.Filled.DragHandle,
                                contentDescription = "Drag to reorder",
                                tint = TextDim,
                                modifier = Modifier
                                    .size(24.dp)
                                    .longPressDraggableHandle(),
                            )

                            Spacer(modifier = Modifier.width(8.dp))

                            // Artwork thumbnail
                            val artworkUrl = favorite.artworkPath?.let {
                                "${ApiClient.BASE_URL.trimEnd('/')}/api/episodes/${favorite.episodeId}/artwork"
                            }
                            if (artworkUrl != null) {
                                AsyncImage(
                                    model = artworkUrl,
                                    contentDescription = favorite.episodeTitle,
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
                                    text = favorite.displayArtistTitle,
                                    color = White,
                                    fontSize = 14.sp,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                                Text(
                                    text = "${favorite.episodeTitle ?: "Unknown episode"} · ${favorite.timestamp}",
                                    color = TextSecondary,
                                    fontSize = 12.sp,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                            }

                            IconButton(onClick = { favVm.unfavorite(favorite.episodeId, favorite.position) }) {
                                Icon(
                                    imageVector = Icons.Filled.Favorite,
                                    contentDescription = "Remove from favorites",
                                    tint = AccentRed,
                                )
                            }
                        }
                        HorizontalDivider(color = Border, thickness = 0.5.dp)
                    }
                }
            }
        }
    }
}
