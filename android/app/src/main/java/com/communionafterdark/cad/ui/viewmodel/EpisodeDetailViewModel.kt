package com.communionafterdark.cad.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.communionafterdark.cad.data.CadRepository
import com.communionafterdark.cad.data.model.Episode
import com.communionafterdark.cad.data.model.Track
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class EpisodeDetailUiState(
    val episode: Episode? = null,
    val tracks: List<Track> = emptyList(),
    val favoritedPositions: Set<Int> = emptySet(),
    val isLoading: Boolean = false,
    val error: String? = null,
)

class EpisodeDetailViewModel : ViewModel() {

    private val repository = CadRepository()

    private val _uiState = MutableStateFlow(EpisodeDetailUiState())
    val uiState: StateFlow<EpisodeDetailUiState> = _uiState.asStateFlow()

    fun toggleFavorite(episodeId: Int, position: Int) {
        _uiState.update {
            val newFavs = if (position in it.favoritedPositions)
                it.favoritedPositions - position
            else
                it.favoritedPositions + position
            it.copy(favoritedPositions = newFavs)
        }
        viewModelScope.launch {
            repository.toggleFavorite(episodeId, position)
        }
    }

    fun loadEpisode(id: Int) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }

            repository.getEpisode(id).onSuccess { episode ->
                _uiState.update { it.copy(episode = episode) }
            }.onFailure { e ->
                _uiState.update { it.copy(error = "Failed to load episode: ${e.message}", isLoading = false) }
                return@launch
            }

            repository.getTracks(id).onSuccess { tracks ->
                _uiState.update { it.copy(tracks = tracks, isLoading = false) }
            }.onFailure { e ->
                _uiState.update { it.copy(error = "Failed to load tracks: ${e.message}", isLoading = false) }
            }
        }
    }
}
