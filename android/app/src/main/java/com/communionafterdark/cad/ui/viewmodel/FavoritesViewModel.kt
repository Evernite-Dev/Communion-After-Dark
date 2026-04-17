package com.communionafterdark.cad.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.communionafterdark.cad.data.CadRepository
import com.communionafterdark.cad.data.model.Favorite
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class FavoritesUiState(
    val favorites: List<Favorite> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
)

class FavoritesViewModel : ViewModel() {

    private val repository = CadRepository()

    private val _uiState = MutableStateFlow(FavoritesUiState())
    val uiState: StateFlow<FavoritesUiState> = _uiState.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            repository.getFavorites().onSuccess { favorites ->
                _uiState.update { it.copy(favorites = favorites, isLoading = false) }
            }.onFailure { e ->
                _uiState.update { it.copy(error = "Failed to load favorites: ${e.message}", isLoading = false) }
            }
        }
    }

    fun unfavorite(episodeId: Int, position: Int) {
        _uiState.update { state ->
            state.copy(favorites = state.favorites.filter {
                !(it.episodeId == episodeId && it.position == position)
            })
        }
        viewModelScope.launch {
            repository.toggleFavorite(episodeId, position)
        }
    }

    fun reorder(fromIndex: Int, toIndex: Int) {
        _uiState.update { state ->
            val list = state.favorites.toMutableList()
            list.add(toIndex, list.removeAt(fromIndex))
            state.copy(favorites = list)
        }
    }
}
