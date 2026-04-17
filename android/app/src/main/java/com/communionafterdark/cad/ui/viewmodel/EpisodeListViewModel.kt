package com.communionafterdark.cad.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.communionafterdark.cad.data.CadRepository
import com.communionafterdark.cad.data.model.Episode
import com.communionafterdark.cad.data.model.Year
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class EpisodeListUiState(
    val years: List<Year> = emptyList(),
    val episodes: List<Episode> = emptyList(),
    val selectedYear: Int? = null,   // null = All
    val isLoading: Boolean = false,
    val error: String? = null,
    val bannerEpisode: Episode? = null,  // newest episode for banner
)

class EpisodeListViewModel : ViewModel() {

    private val repository = CadRepository()

    private val _uiState = MutableStateFlow(EpisodeListUiState())
    val uiState: StateFlow<EpisodeListUiState> = _uiState.asStateFlow()

    init {
        loadYearsAndEpisodes()
    }

    private fun loadYearsAndEpisodes() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }

            // Load years
            repository.getYears().onSuccess { years ->
                _uiState.update { it.copy(years = years) }
            }.onFailure { e ->
                _uiState.update { it.copy(error = "Failed to load years: ${e.message}") }
            }

            // Load episodes (all years, audio only)
            repository.getEpisodes(year = null, audioOnly = true).onSuccess { episodes ->
                val banner = episodes.firstOrNull()
                _uiState.update { it.copy(episodes = episodes, bannerEpisode = banner, isLoading = false) }
            }.onFailure { e ->
                _uiState.update { it.copy(error = "Failed to load episodes: ${e.message}", isLoading = false) }
            }
        }
    }

    fun selectYear(year: Int?) {
        _uiState.update { it.copy(selectedYear = year, isLoading = true, error = null) }
        viewModelScope.launch {
            repository.getEpisodes(year = year, audioOnly = true).onSuccess { episodes ->
                _uiState.update { it.copy(episodes = episodes, isLoading = false) }
            }.onFailure { e ->
                _uiState.update { it.copy(error = "Failed to load episodes: ${e.message}", isLoading = false) }
            }
        }
    }

    fun dismissBanner() {
        _uiState.update { it.copy(bannerEpisode = null) }
    }
}
