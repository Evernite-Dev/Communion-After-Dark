package com.communionafterdark.cad.ui.components

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.communionafterdark.cad.data.model.Year
import com.communionafterdark.cad.ui.theme.AccentRed
import com.communionafterdark.cad.ui.theme.Border
import com.communionafterdark.cad.ui.theme.Surface
import com.communionafterdark.cad.ui.theme.TextSecondary
import com.communionafterdark.cad.ui.theme.White

@Composable
fun YearFilterRow(
    years: List<Year>,
    selectedYear: Int?,
    onYearSelected: (Int?) -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .horizontalScroll(rememberScrollState())
            .padding(horizontal = 8.dp, vertical = 4.dp),
    ) {
        // "All" chip
        YearChip(
            label = "All",
            selected = selectedYear == null,
            onClick = { onYearSelected(null) },
        )

        years.forEach { year ->
            YearChip(
                label = year.year.toString(),
                selected = selectedYear == year.year,
                onClick = { onYearSelected(year.year) },
            )
        }
    }
}

@Composable
private fun YearChip(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    FilterChip(
        selected = selected,
        onClick = onClick,
        label = {
            Text(
                text = label,
                color = if (selected) White else TextSecondary,
            )
        },
        modifier = modifier.padding(horizontal = 4.dp),
        colors = FilterChipDefaults.filterChipColors(
            selectedContainerColor = AccentRed,
            containerColor = Surface,
        ),
        border = FilterChipDefaults.filterChipBorder(
            enabled = true,
            selected = selected,
            borderColor = Border,
            selectedBorderColor = AccentRed,
        ),
    )
}
