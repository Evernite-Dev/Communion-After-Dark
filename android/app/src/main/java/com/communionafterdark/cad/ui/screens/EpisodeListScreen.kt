package com.communionafterdark.cad.ui.screens

import androidx.compose.foundation.background
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
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.communionafterdark.cad.data.api.ApiClient
import com.communionafterdark.cad.ui.components.YearFilterRow
import com.communionafterdark.cad.ui.theme.Border
import com.communionafterdark.cad.ui.theme.SurfaceVariant
import com.communionafterdark.cad.ui.theme.TextDim
import com.communionafterdark.cad.ui.theme.TextSecondary
import com.communionafterdark.cad.ui.theme.White
import com.communionafterdark.cad.ui.viewmodel.EpisodeListViewModel
import com.communionafterdark.cad.ui.viewmodel.PlayerViewModel

@Composable
fun EpisodeListScreen(
    listVm: EpisodeListViewModel,
    playerVm: PlayerViewModel,
    onEpisodeClick: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val uiState by listVm.uiState.collectAsState()

    Column(modifier = modifier.fillMaxSize()) {
        // Year filter chips
        YearFilterRow(
            years = uiState.years,
            selectedYear = uiState.selectedYear,
            onYearSelected = { listVm.selectYear(it) },
        )

        HorizontalDivider(color = Border)

        when {
            uiState.isLoading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }
            uiState.error != null -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(
                        text = uiState.error ?: "Unknown error",
                        color = TextSecondary,
                    )
                }
            }
            uiState.episodes.isEmpty() -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(
                        text = "No episodes available",
                        color = TextDim,
                    )
                }
            }
            else -> {
                LazyColumn(modifier = Modifier.fillMaxSize()) {
                    items(uiState.episodes, key = { it.id }) { episode ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { onEpisodeClick(episode.id) }
                                .padding(horizontal = 12.dp, vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            // Artwork thumbnail — always attempt; Box provides fallback bg + icon
                            Box(
                                modifier = Modifier
                                    .size(56.dp)
                                    .background(SurfaceVariant),
                                contentAlignment = Alignment.Center,
                            ) {
                                Icon(
                                    imageVector = Icons.Filled.MusicNote,
                                    contentDescription = null,
                                    tint = TextDim,
                                    modifier = Modifier.size(28.dp),
                                )
                                AsyncImage(
                                    model = episode.artworkUrl(ApiClient.BASE_URL),
                                    contentDescription = episode.displayTitle,
                                    contentScale = ContentScale.Crop,
                                    modifier = Modifier.size(56.dp),
                                )
                            }

                            Spacer(modifier = Modifier.width(12.dp))

                            // Episode info
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = episode.displayTitle,
                                    color = White,
                                    fontSize = 15.sp,
                                    fontWeight = FontWeight.Normal,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                                Text(
                                    text = episode.pubDate ?: "",
                                    color = TextSecondary,
                                    fontSize = 13.sp,
                                )
                            }

                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.KeyboardArrowRight,
                                contentDescription = null,
                                tint = TextDim,
                            )
                        }
                        HorizontalDivider(color = Border, thickness = 0.5.dp)
                    }
                }
            }
        }
    }
}
