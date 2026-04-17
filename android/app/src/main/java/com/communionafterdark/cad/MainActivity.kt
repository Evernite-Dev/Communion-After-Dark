package com.communionafterdark.cad

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.automirrored.filled.QueueMusic
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import com.communionafterdark.cad.data.CadRepository
import kotlinx.coroutines.launch
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.communionafterdark.cad.ui.components.BannerSection
import com.communionafterdark.cad.ui.components.MiniPlayer
import com.communionafterdark.cad.ui.nav.Screen
import com.communionafterdark.cad.ui.screens.EpisodeDetailScreen
import com.communionafterdark.cad.ui.screens.EpisodeListScreen
import com.communionafterdark.cad.ui.screens.FavoritesScreen
import com.communionafterdark.cad.ui.screens.SearchScreen
import com.communionafterdark.cad.ui.theme.AccentRed
import com.communionafterdark.cad.ui.theme.Black
import com.communionafterdark.cad.ui.theme.CadTheme
import com.communionafterdark.cad.ui.theme.TextDim
import com.communionafterdark.cad.ui.theme.TextSecondary
import com.communionafterdark.cad.ui.theme.White
import com.communionafterdark.cad.ui.viewmodel.EpisodeDetailViewModel
import com.communionafterdark.cad.ui.viewmodel.EpisodeListViewModel
import com.communionafterdark.cad.ui.viewmodel.FavoritesViewModel
import com.communionafterdark.cad.ui.viewmodel.PlayerViewModel
import com.communionafterdark.cad.ui.viewmodel.SearchViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            CadTheme {
                CadApp(
                    playerVmFactory = PlayerViewModel.Factory(applicationContext),
                )
            }
        }
    }
}

@Composable
fun CadApp(
    playerVmFactory: PlayerViewModel.Factory,
) {
    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = navBackStackEntry?.destination

    val listVm: EpisodeListViewModel = viewModel()
    val detailVm: EpisodeDetailViewModel = viewModel()
    val favVm: FavoritesViewModel = viewModel()
    val searchVm: SearchViewModel = viewModel()
    val playerVm: PlayerViewModel = viewModel(factory = playerVmFactory)

    val listState by listVm.uiState.collectAsState()
    val playerState by playerVm.state.collectAsState()
    val repository = remember { CadRepository() }
    val scope = rememberCoroutineScope()

    Scaffold(
        modifier = Modifier
            .fillMaxSize()
            .background(Black),
        containerColor = Black,
        bottomBar = {
            Column {
                // Mini player — shown when an episode is loaded
                if (playerState.episode != null) {
                    MiniPlayer(
                        state = playerState,
                        onTogglePlay = { playerVm.togglePlayPause() },
                        onPrev = { /* placeholder */ },
                        onNext = { /* placeholder */ },
                        onSeek = { fraction ->
                            playerVm.seekTo((fraction * playerState.durationMs).toLong())
                        },
                        onSeekToTimestamp = { ts -> playerVm.seekToTimestamp(ts) },
                        onToggleFavorite = { position ->
                            playerState.episode?.id?.let { episodeId ->
                                playerVm.toggleFavorite(episodeId, position)
                            }
                        },
                        onArtworkClick = {
                            playerState.episode?.id?.let { episodeId ->
                                navController.navigate(Screen.EpisodeDetail.route(episodeId)) {
                                    launchSingleTop = true
                                }
                            }
                        },
                    )
                }

                // Bottom navigation bar
                NavigationBar(
                    containerColor = Black,
                ) {
                    NavigationBarItem(
                        selected = currentDestination?.hierarchy?.any {
                            it.route == Screen.EpisodeList.route
                        } == true,
                        onClick = {
                            navController.navigate(Screen.EpisodeList.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = {
                            Icon(Icons.AutoMirrored.Filled.QueueMusic, contentDescription = "Episodes")
                        },
                        label = { Text("Episodes") },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = AccentRed,
                            selectedTextColor = AccentRed,
                            unselectedIconColor = TextSecondary,
                            unselectedTextColor = TextSecondary,
                            indicatorColor = Black,
                        ),
                    )
                    NavigationBarItem(
                        selected = currentDestination?.hierarchy?.any {
                            it.route == Screen.Favorites.route
                        } == true,
                        onClick = {
                            navController.navigate(Screen.Favorites.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = {
                            Icon(Icons.Filled.Favorite, contentDescription = "Favorites")
                        },
                        label = { Text("Favorites") },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = AccentRed,
                            selectedTextColor = AccentRed,
                            unselectedIconColor = TextSecondary,
                            unselectedTextColor = TextSecondary,
                            indicatorColor = Black,
                        ),
                    )
                    NavigationBarItem(
                        selected = currentDestination?.hierarchy?.any {
                            it.route == Screen.Search.route
                        } == true,
                        onClick = {
                            navController.navigate(Screen.Search.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = {
                            Icon(Icons.Filled.Search, contentDescription = "Search")
                        },
                        label = { Text("Search") },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = AccentRed,
                            selectedTextColor = AccentRed,
                            unselectedIconColor = TextSecondary,
                            unselectedTextColor = TextSecondary,
                            indicatorColor = Black,
                        ),
                    )
                }
            }
        },
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Screen.EpisodeList.route,
            modifier = Modifier.padding(innerPadding),
        ) {
            composable(Screen.EpisodeList.route) {
                Column(modifier = Modifier.fillMaxSize()) {
                    BannerSection(
                        bannerEpisode = listState.bannerEpisode,
                        playerState = playerState,
                        onBannerClick = { ep ->
                            listVm.dismissBanner()
                            navController.navigate(Screen.EpisodeDetail.route(ep.id))
                            scope.launch {
                                val tracks = repository.getTracks(ep.id).getOrDefault(emptyList())
                                playerVm.playEpisode(ep, tracks)
                            }
                        },
                    )
                    EpisodeListScreen(
                        listVm = listVm,
                        playerVm = playerVm,
                        onEpisodeClick = { id ->
                            navController.navigate(Screen.EpisodeDetail.route(id))
                        },
                    )
                }
            }

            composable(
                route = Screen.EpisodeDetail.route,
                arguments = listOf(
                    navArgument(Screen.EpisodeDetail.ARG) { type = NavType.IntType }
                ),
            ) { backStackEntry ->
                val episodeId = backStackEntry.arguments?.getInt(Screen.EpisodeDetail.ARG) ?: return@composable
                EpisodeDetailScreen(
                    episodeId = episodeId,
                    detailVm = detailVm,
                    playerVm = playerVm,
                    onBack = { navController.popBackStack() },
                    modifier = Modifier.fillMaxSize(),
                )
            }

            composable(Screen.Favorites.route) {
                FavoritesScreen(
                    favVm = favVm,
                    playerVm = playerVm,
                    onEpisodeClick = { id ->
                        navController.navigate(Screen.EpisodeDetail.route(id))
                    },
                    modifier = Modifier.fillMaxSize(),
                )
            }

            composable(Screen.Search.route) {
                SearchScreen(
                    searchVm = searchVm,
                    onEpisodeClick = { id ->
                        navController.navigate(Screen.EpisodeDetail.route(id))
                    },
                    onTrackPlay = { episodeId, timestamp ->
                        scope.launch {
                            val episode = repository.getEpisode(episodeId).getOrNull() ?: return@launch
                            val tracks = repository.getTracks(episodeId).getOrDefault(emptyList())
                            playerVm.playEpisode(episode, tracks)
                            playerVm.seekToTimestamp(timestamp)
                        }
                    },
                    modifier = Modifier.fillMaxSize(),
                )
            }
        }
    }
}
