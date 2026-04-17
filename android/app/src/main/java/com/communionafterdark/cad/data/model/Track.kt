package com.communionafterdark.cad.data.model

import com.google.gson.annotations.SerializedName

data class Track(
    val id: Int,
    @SerializedName("episode_id") val episodeId: Int,
    val position: Int,
    val timestamp: String,
    val artist: String,
    val title: String,
    val album: String? = null,
    val label: String? = null,
    val country: String? = null,
)
