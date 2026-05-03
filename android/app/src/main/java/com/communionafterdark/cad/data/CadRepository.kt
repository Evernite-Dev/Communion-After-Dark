package com.communionafterdark.cad.data

import com.communionafterdark.cad.data.api.ApiClient
import com.communionafterdark.cad.data.api.SearchResult
import com.communionafterdark.cad.data.model.Episode
import com.communionafterdark.cad.data.model.Favorite
import com.communionafterdark.cad.data.model.Track
import com.communionafterdark.cad.data.model.Year
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class CadRepository {

    private val api = ApiClient.api

    suspend fun getYears(): Result<List<Year>> = runCatching {
        withContext(Dispatchers.IO) { api.getYears() }
    }

    suspend fun getEpisodes(year: Int? = null, audioOnly: Boolean = true, limit: Int = 200): Result<List<Episode>> =
        runCatching {
            withContext(Dispatchers.IO) { api.getEpisodes(year = year, audioOnly = audioOnly, limit = limit) }
        }

    suspend fun getEpisode(id: Int): Result<Episode> = runCatching {
        withContext(Dispatchers.IO) { api.getEpisode(id) }
    }

    suspend fun getTracks(id: Int): Result<List<Track>> = runCatching {
        withContext(Dispatchers.IO) { api.getTracks(id) }
    }

    suspend fun search(q: String): Result<List<SearchResult>> = runCatching {
        withContext(Dispatchers.IO) { api.search(q) }
    }

    suspend fun getFavorites(): Result<List<Favorite>> = runCatching {
        withContext(Dispatchers.IO) { api.getFavorites() }
    }

    suspend fun toggleFavorite(episodeId: Int, position: Int): Result<Boolean> = runCatching {
        withContext(Dispatchers.IO) {
            api.toggleFavorite(episodeId, position).favorited
        }
    }
}
