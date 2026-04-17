package com.communionafterdark.cad.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import com.communionafterdark.cad.R

val MinervaModern = FontFamily(
    // Bold.ttf → lightest upright weight (treated as Normal/400)
    Font(R.font.minervamodern_bold, weight = FontWeight.Normal, style = FontStyle.Normal),
    // Italic.ttf → normal weight italic
    Font(R.font.minervamodern_italic, weight = FontWeight.Normal, style = FontStyle.Italic),
    // Black.ttf → bold weight (700)
    Font(R.font.minervamodern_black, weight = FontWeight.Bold, style = FontStyle.Normal),
    // BoldItalic.ttf → bold italic
    Font(R.font.minervamodern_bolditalic, weight = FontWeight.Bold, style = FontStyle.Italic),
    // BlackItalic.ttf → extra-bold (900)
    Font(R.font.minervamodern_blackitalic, weight = FontWeight.ExtraBold, style = FontStyle.Normal),
)

val CadTypography = Typography(
    // Display — episode hero title, banner
    displayLarge = TextStyle(
        fontFamily = MinervaModern,
        fontWeight = FontWeight.Bold,
        fontSize = 50.sp,
        color = White,
    ),
    displayMedium = TextStyle(
        fontFamily = MinervaModern,
        fontWeight = FontWeight.Bold,
        fontSize = 42.sp,
        color = White,
    ),
    displaySmall = TextStyle(
        fontFamily = MinervaModern,
        fontWeight = FontWeight.Bold,
        fontSize = 36.sp,
        color = White,
    ),
    // Headline — screen titles, section headers
    headlineLarge = TextStyle(
        fontFamily = MinervaModern,
        fontWeight = FontWeight.Bold,
        fontSize = 28.sp,
        color = White,
    ),
    headlineMedium = TextStyle(
        fontFamily = MinervaModern,
        fontWeight = FontWeight.Bold,
        fontSize = 24.sp,
        color = White,
    ),
    headlineSmall = TextStyle(
        fontFamily = MinervaModern,
        fontWeight = FontWeight.Bold,
        fontSize = 20.sp,
        color = White,
    ),
    // Title — list item titles, card titles
    titleLarge = TextStyle(
        fontFamily = MinervaModern,
        fontWeight = FontWeight.Normal,
        fontSize = 20.sp,
        color = White,
    ),
    titleMedium = TextStyle(
        fontFamily = MinervaModern,
        fontWeight = FontWeight.Normal,
        fontSize = 16.sp,
        color = White,
    ),
    titleSmall = TextStyle(
        fontFamily = MinervaModern,
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        color = White,
    ),
    // Body — descriptions, secondary text
    bodyLarge = TextStyle(
        fontFamily = MinervaModern,
        fontWeight = FontWeight.Normal,
        fontSize = 16.sp,
        color = TextSecondary,
    ),
    bodyMedium = TextStyle(
        fontFamily = MinervaModern,
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        color = TextSecondary,
    ),
    bodySmall = TextStyle(
        fontFamily = MinervaModern,
        fontWeight = FontWeight.Normal,
        fontSize = 12.sp,
        color = TextSecondary,
    ),
    // Label — chips, tabs, navigation
    labelLarge = TextStyle(
        fontFamily = MinervaModern,
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        color = TextSecondary,
    ),
    labelMedium = TextStyle(
        fontFamily = MinervaModern,
        fontWeight = FontWeight.Normal,
        fontSize = 12.sp,
        color = TextSecondary,
    ),
    labelSmall = TextStyle(
        fontFamily = MinervaModern,
        fontWeight = FontWeight.Normal,
        fontSize = 11.sp,
        color = TextSecondary,
    ),
)
