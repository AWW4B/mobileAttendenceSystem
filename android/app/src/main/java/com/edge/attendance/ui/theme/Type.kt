package com.edge.attendance.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.ExperimentalTextApi
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import com.edge.attendance.R

/*
 * Albert Sans carries language; JetBrains Mono carries IDs and measurements.
 * Both are OFL variable fonts bundled in res/font (licences in design/licenses).
 * Sizes are sp so text follows the system font-size setting.
 */
@OptIn(ExperimentalTextApi::class)
private fun albert(weight: Int) = Font(
    R.font.albertsans, FontWeight(weight),
    variationSettings = FontVariation.Settings(FontVariation.weight(weight)),
)

@OptIn(ExperimentalTextApi::class)
private fun mono(weight: Int) = Font(
    R.font.jetbrainsmono, FontWeight(weight),
    variationSettings = FontVariation.Settings(FontVariation.weight(weight)),
)

val AlbertSans = FontFamily(albert(400), albert(500), albert(560), albert(600), albert(620))
val JetBrainsMono = FontFamily(mono(400), mono(500), mono(600))

private fun style(size: Int, line: Int, weight: Int, tracking: Double = 0.0, family: FontFamily = AlbertSans) = TextStyle(
    fontFamily = family, fontSize = size.sp, lineHeight = line.sp,
    fontWeight = FontWeight(weight), letterSpacing = tracking.sp,
)

val EdgeTypography = Typography(
    headlineMedium = style(26, 32, 620, -0.3),   // screen titles
    headlineSmall = style(22, 28, 600, -0.2),
    titleLarge = style(20, 28, 600),
    titleMedium = style(16, 24, 600),            // row titles
    titleSmall = style(14, 20, 600),
    bodyLarge = style(16, 24, 400),
    bodyMedium = style(14, 20, 400),
    bodySmall = style(12, 16, 400),
    labelLarge = style(15, 20, 560),             // buttons
    labelMedium = style(12, 16, 560),            // chips
    labelSmall = style(11, 16, 500),
)

/** Roll numbers, URLs, counts. */
val MonoBody = style(13, 18, 400, family = JetBrainsMono)
val MonoLabel = style(12, 16, 500, family = JetBrainsMono)
