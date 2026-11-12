package com.edge.attendance.ui.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color

/*
 * Colour roles mirror server/portal/static/css/tokens.css. One accent (verdigris)
 * for primary actions and "confirmed"; tertiary is "needs a look" (amber); error is
 * absence. Do not add colours here without adding them to the web tokens.
 *
 *   primary            --accent         present / confirmed / primary actions
 *   tertiary           --review         matches that need the teacher's check
 *   error              --absent         absent
 *   surface            --paper          screen canvas
 *   surfaceContainer*  --surface(-2)    lists, bars, fills
 *   outlineVariant     --line           hairlines
 */
private val Ink = Color(0xFF161A17)
private val Paper = Color(0xFFF6F7F5)

val LightColors: ColorScheme = lightColorScheme(
    primary = Color(0xFF1B5E57), onPrimary = Color.White,
    primaryContainer = Color(0xFFE5F0EE), onPrimaryContainer = Color(0xFF0F3A35),
    secondary = Color(0xFF454D45), onSecondary = Color.White,
    secondaryContainer = Color(0xFFE9ECE8), onSecondaryContainer = Ink,
    tertiary = Color(0xFF84560A), onTertiary = Color.White,
    tertiaryContainer = Color(0xFFF7EED8), onTertiaryContainer = Color(0xFF84560A),
    error = Color(0xFFA1313A), onError = Color.White,
    errorContainer = Color(0xFFFAEBEB), onErrorContainer = Color(0xFFA1313A),
    background = Paper, onBackground = Ink,
    surface = Paper, onSurface = Ink,
    surfaceVariant = Color(0xFFEFF1EE), onSurfaceVariant = Color(0xFF5F685F),
    outline = Color(0xFFC8CEC6), outlineVariant = Color(0xFFE1E5DF),
    surfaceContainerLowest = Color.White, surfaceContainerLow = Color.White,
    surfaceContainer = Color(0xFFEFF1EE), surfaceContainerHigh = Color(0xFFE9ECE8),
    surfaceContainerHighest = Color(0xFFE1E5DF),
    inverseSurface = Ink, inverseOnSurface = Paper, inversePrimary = Color(0xFF72C4B8),
    scrim = Color.Black,
)

val DarkColors: ColorScheme = darkColorScheme(
    primary = Color(0xFF72C4B8), onPrimary = Color(0xFF0A1512),
    primaryContainer = Color(0xFF14302C), onPrimaryContainer = Color(0xFF72C4B8),
    secondary = Color(0xFFB5BDB4), onSecondary = Color(0xFF0F1311),
    secondaryContainer = Color(0xFF212823), onSecondaryContainer = Color(0xFFE8ECE7),
    tertiary = Color(0xFFE4B862), onTertiary = Color(0xFF241A04),
    tertiaryContainer = Color(0xFF33290F), onTertiaryContainer = Color(0xFFE4B862),
    error = Color(0xFFF19A96), onError = Color(0xFF2A0D0F),
    errorContainer = Color(0xFF3B1F20), onErrorContainer = Color(0xFFF19A96),
    background = Color(0xFF0F1311), onBackground = Color(0xFFE8ECE7),
    surface = Color(0xFF0F1311), onSurface = Color(0xFFE8ECE7),
    surfaceVariant = Color(0xFF1A201C), onSurfaceVariant = Color(0xFF8F998F),
    outline = Color(0xFF37433C), outlineVariant = Color(0xFF262E29),
    surfaceContainerLowest = Color(0xFF0B0E0C), surfaceContainerLow = Color(0xFF151A17),
    surfaceContainer = Color(0xFF1A201C), surfaceContainerHigh = Color(0xFF212823),
    surfaceContainerHighest = Color(0xFF262E29),
    inverseSurface = Color(0xFFE8ECE7), inverseOnSurface = Color(0xFF161A17), inversePrimary = Color(0xFF1B5E57),
    scrim = Color.Black,
)

/** The camera screen is always dark, in either theme, like a camera app. */
object CameraColors {
    val Background = Color(0xFF0C0F0D)
    val OnBackground = Color(0xFFEEF2ED)
    val Muted = Color(0xB3EEF2ED)
    val Chip = Color(0x17FFFFFF)
    val Hairline = Color(0x14FFFFFF)
}
