package com.communionafterdark.cad.ui.components

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.communionafterdark.cad.data.api.ApiClient
import com.communionafterdark.cad.data.model.Episode
import com.communionafterdark.cad.ui.theme.AccentRed
import com.communionafterdark.cad.ui.theme.Black
import com.communionafterdark.cad.ui.theme.TextSecondary
import com.communionafterdark.cad.ui.theme.White
import com.communionafterdark.cad.ui.viewmodel.PlaybackState
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

private fun formatBannerDate(dateStr: String?): String {
    if (dateStr.isNullOrBlank()) return ""
    return try {
        val date = LocalDate.parse(dateStr)
        date.format(DateTimeFormatter.ofPattern("MMMM d, yyyy", Locale.ENGLISH))
    } catch (e: Exception) {
        dateStr
    }
}

// Two distinct state types for AnimatedContent
private sealed class BannerState {
    object Logo : BannerState()
    data class NewEpisode(val episode: Episode) : BannerState()
}

@Composable
fun BannerSection(
    bannerEpisode: Episode?,
    playerState: PlaybackState,
    onBannerClick: (Episode) -> Unit,
    modifier: Modifier = Modifier,
) {
    // Show episode banner when there is a bannerEpisode and it's not currently playing
    val bannerState: BannerState = if (bannerEpisode != null && playerState.episode?.id != bannerEpisode.id) {
        BannerState.NewEpisode(bannerEpisode)
    } else {
        BannerState.Logo
    }

    AnimatedContent(
        targetState = bannerState,
        transitionSpec = { fadeIn() togetherWith fadeOut() },
        label = "banner_anim",
        modifier = modifier
            .fillMaxWidth()
            .height(120.dp)
            .background(Black),
    ) { state ->
        when (state) {
            is BannerState.Logo -> {
                AsyncImage(
                    model = "file:///android_asset/cad_banner.jpg",
                    contentDescription = "Communion After Dark",
                    contentScale = ContentScale.Crop,
                    alignment = androidx.compose.ui.Alignment.Center.let {
                        androidx.compose.ui.BiasAlignment(horizontalBias = -0.08f, verticalBias = 0f)
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(120.dp),
                )
            }
            is BannerState.NewEpisode -> {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(120.dp)
                        .clickable { onBannerClick(state.episode) },
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    // Left: square episode artwork
                    AsyncImage(
                        model = state.episode.artworkUrl(ApiClient.BASE_URL),
                        contentDescription = state.episode.displayTitle,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier.size(120.dp),
                    )
                    // Right: episode info
                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .padding(horizontal = 16.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Text(
                            text = "NEW EPISODE",
                            color = AccentRed,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 0.15.sp,
                        )
                        Text(
                            text = state.episode.displayTitle,
                            color = White,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Text(
                            text = formatBannerDate(state.episode.pubDate),
                            color = TextSecondary,
                            fontSize = 13.sp,
                        )
                    }
                }
            }
        }
    }
}
