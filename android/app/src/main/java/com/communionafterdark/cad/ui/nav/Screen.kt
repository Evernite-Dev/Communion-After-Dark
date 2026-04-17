package com.communionafterdark.cad.ui.nav

sealed class Screen(val route: String) {
    object EpisodeList : Screen("episodes")
    object Favorites : Screen("favorites")
    object Search : Screen("search")
    object EpisodeDetail : Screen("episode/{episodeId}") {
        fun route(id: Int) = "episode/$id"
        const val ARG = "episodeId"
    }
}
