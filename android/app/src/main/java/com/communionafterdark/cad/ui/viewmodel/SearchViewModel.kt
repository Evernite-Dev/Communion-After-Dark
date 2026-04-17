package com.communionafterdark.cad.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.communionafterdark.cad.data.CadRepository
import com.communionafterdark.cad.data.api.SearchResult
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SearchUiState(
    val results: List<SearchResult> = emptyList(),
    val favoritedKeys: Set<String> = emptySet(),
    val query: String = "",
    val isLoading: Boolean = false,
    val error: String? = null,
)

class SearchViewModel : ViewModel() {

    private val repository = CadRepository()

    private val _uiState = MutableStateFlow(SearchUiState())
    val uiState: StateFlow<SearchUiState> = _uiState.asStateFlow()

    private var searchJob: Job? = null

    fun toggleFavorite(episodeId: Int, position: Int) {
        val key = "${episodeId}_${position}"
        _uiState.update {
            val newKeys = if (key in it.favoritedKeys) it.favoritedKeys - key else it.favoritedKeys + key
            it.copy(favoritedKeys = newKeys)
        }
        viewModelScope.launch {
            repository.toggleFavorite(episodeId, position)
        }
    }

    fun search(q: String) {
        _uiState.update { it.copy(query = q) }
        searchJob?.cancel()

        if (q.trim().length < 2) {
            _uiState.update { it.copy(results = emptyList(), isLoading = false) }
            return
        }

        searchJob = viewModelScope.launch {
            // 300ms debounce
            delay(300)
            _uiState.update { it.copy(isLoading = true, error = null) }
            repository.search(q).onSuccess { results ->
                _uiState.update { it.copy(results = results, isLoading = false) }
            }.onFailure { e ->
                _uiState.update { it.copy(error = "Search failed: ${e.message}", isLoading = false) }
            }
        }
    }
}
