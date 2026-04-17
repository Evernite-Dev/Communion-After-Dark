package com.communionafterdark.cad.data.model

import com.google.gson.annotations.SerializedName

data class Year(
    val year: Int,
    val total: Int,
    @SerializedName("with_audio") val withAudio: Int,
    @SerializedName("no_audio") val noAudio: Int,
)
