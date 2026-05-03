package com.communionafterdark.cad.widget

import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey

object CadWidgetKeys {
    val titleKey = stringPreferencesKey("cad_title")
    val trackNameKey = stringPreferencesKey("cad_track_name")
    val isPlayingKey = booleanPreferencesKey("cad_is_playing")
    val artworkPathKey = stringPreferencesKey("cad_artwork_path")
    val episodeIdKey = intPreferencesKey("cad_episode_id")
}
