package com.communionafterdark.cad.data.api

import com.communionafterdark.cad.data.model.Episode
import com.communionafterdark.cad.data.model.Favorite
import com.communionafterdark.cad.data.model.Track
import com.communionafterdark.cad.data.model.Year
import com.google.gson.annotations.SerializedName
import retrofit2.http.GET
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

data class SearchResult(
    val id: Int,
    @SerializedName("episode_id") val episodeId: Int,
    val position: Int,
    val timestamp: String,
    val artist: String,
    val title: String,
    val album: String? = null,
    @SerializedName("episode_title") val episodeTitle: String? = null,
    @SerializedName("pub_date") val pubDate: String? = null,
    val year: Int? = null,
    @SerializedName("audio_path") val audioPath: String? = null,
    @SerializedName("artwork_path") val artworkPath: String? = null,
) {
    fun artworkUrl(base: String) = "${base.trimEnd('/')}/api/episodes/$episodeId/artwork"
}

data class FavoriteToggleResult(
    val favorited: Boolean,
)

interface CadApi {

    @GET("api/years")
    suspend fun getYears(): List<Year>

    @GET("api/episodes")
    suspend fun getEpisodes(
        @Query("year") year: Int? = null,
        @Query("audio_only") audioOnly: Boolean = true,
        @Query("limit") limit: Int = 200,
        @Query("offset") offset: Int = 0,
    ): List<Episode>

    @GET("api/episodes/{id}")
    suspend fun getEpisode(@Path("id") id: Int): Episode

    @GET("api/episodes/{id}/tracks")
    suspend fun getTracks(@Path("id") id: Int): List<Track>

    @GET("api/search")
    suspend fun search(
        @Query("q") q: String,
        @Query("limit") limit: Int = 50,
    ): List<SearchResult>

    @GET("api/favorites")
    suspend fun getFavorites(): List<Favorite>

    @PUT("api/favorites/{episodeId}/{position}")
    suspend fun toggleFavorite(
        @Path("episodeId") episodeId: Int,
        @Path("position") position: Int,
    ): FavoriteToggleResult
}
