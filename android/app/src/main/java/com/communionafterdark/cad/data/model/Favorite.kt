package com.communionafterdark.cad.data.model

import com.google.gson.annotations.SerializedName

data class Favorite(
    val id: Int,
    @SerializedName("episode_id") val episodeId: Int,
    val position: Int,
    val artist: String,
    val title: String,
    val timestamp: String,
    @SerializedName("episode_title") val episodeTitle: String? = null,
    @SerializedName("pub_date") val pubDate: String? = null,
    @SerializedName("audio_path") val audioPath: String? = null,
    @SerializedName("artwork_path") val artworkPath: String? = null,
    @SerializedName("favorited_at") val favoritedAt: String? = null,
) {
    val displayArtistTitle: String get() = "$artist \u2014 $title"
}
