package com.communionafterdark.cad.data.model

import com.google.gson.annotations.SerializedName

data class Episode(
    val id: Int,
    val title: String?,
    @SerializedName("pub_date") val pubDate: String?,
    val year: Int?,
    val category: String?,
    @SerializedName("audio_status") val audioStatus: String?,
    @SerializedName("artwork_status") val artworkStatus: String?,
    @SerializedName("audio_source") val audioSource: String?,
    @SerializedName("audio_path") val audioPath: String?,
    @SerializedName("artwork_path") val artworkPath: String?,
    @SerializedName("track_count") val trackCount: Int = 0,
    val description: String? = null,
) {
    val displayTitle: String
        get() = title
            ?.removePrefix("Communion After Dark - ")
            ?.removePrefix("Communion After Dark – ")
            ?: "Episode $id"

    val hasAudio: Boolean get() = audioStatus == "done"
    val hasArtwork: Boolean get() = artworkStatus == "done"

    fun artworkUrl(base: String) = "${base.trimEnd('/')}/api/episodes/$id/artwork"
    fun audioUrl(base: String) = "${base.trimEnd('/')}/api/episodes/$id/audio"
}
