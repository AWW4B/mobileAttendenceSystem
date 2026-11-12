package com.edge.attendance.ui

import android.provider.Settings
import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.edge.attendance.ui.screens.CaptureScreen
import com.edge.attendance.ui.screens.DoneScreen
import com.edge.attendance.ui.screens.HomeScreen
import com.edge.attendance.ui.screens.LoginScreen
import com.edge.attendance.ui.screens.NavBarHeight
import com.edge.attendance.ui.screens.ReviewScreen
import com.edge.attendance.ui.theme.EdgeTheme
import com.edge.attendance.ui.theme.Motion
import com.edge.attendance.ui.theme.StatusBarIcons

@Composable
fun AttendanceApp(vm: AttendanceViewModel) {
    EdgeTheme {
        val state by vm.state.collectAsStateWithLifecycle()
        val snackbar = remember { SnackbarHostState() }
        val darkTheme = isSystemInDarkTheme()
        val context = LocalContext.current
        // Honour the system "Remove animations" setting: swap movement for an instant cut.
        val reduceMotion = remember {
            Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
        }

        // System Back always steps out of the current flow; it never traps the user.
        BackHandler(enabled = state.screen != Screen.LOGIN && !(state.screen == Screen.SECTIONS && state.tab == Tab.SECTIONS)) { vm.back() }
        StatusBarIcons(lightIcons = darkTheme || state.screen == Screen.CAPTURE)

        // Transient feedback is a snackbar, not a dialog.
        LaunchedEffect(state.message) {
            val message = state.message ?: return@LaunchedEffect
            snackbar.showSnackbar(message, actionLabel = "Dismiss", duration = SnackbarDuration.Short)
            vm.dismissMessage()
        }

        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            Box(Modifier.fillMaxSize()) {
                AnimatedContent(
                    targetState = state.screen,
                    transitionSpec = {
                        if (reduceMotion) {
                            fadeIn(tween(1)) togetherWith fadeOut(tween(1))
                        } else {
                            val forward = targetState.ordinal > initialState.ordinal
                            (fadeIn(tween(Motion.Base, delayMillis = 40, easing = Motion.EaseOut)) +
                                slideInHorizontally(tween(Motion.Slow, easing = Motion.EaseOut)) { if (forward) it / 14 else -it / 14 }) togetherWith
                                fadeOut(tween(Motion.Fast, easing = Motion.EaseOut))
                        }
                    },
                    label = "screen",
                ) { screen ->
                    when (screen) {
                        Screen.LOGIN -> LoginScreen(state, vm)
                        Screen.SECTIONS -> HomeScreen(state, vm)
                        Screen.CAPTURE -> CaptureScreen(state, vm)
                        Screen.REVIEW -> ReviewScreen(state, vm)
                        Screen.DONE -> DoneScreen(state, vm)
                    }
                }
                if (state.busy && state.screen != Screen.CAPTURE) {
                    LinearProgressIndicator(
                        modifier = Modifier.align(Alignment.TopCenter).fillMaxWidth().height(3.dp),
                        color = MaterialTheme.colorScheme.primary, trackColor = Color.Transparent,
                    )
                }
                SnackbarHost(
                    snackbar,
                    Modifier.align(Alignment.BottomCenter).navigationBarsPadding()
                        .padding(bottom = if (state.screen == Screen.SECTIONS) NavBarHeight else 0.dp),
                )
            }
        }
    }
}
