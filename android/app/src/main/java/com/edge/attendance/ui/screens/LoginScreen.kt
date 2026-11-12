package com.edge.attendance.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.edge.attendance.R
import com.edge.attendance.ui.AttendanceViewModel
import com.edge.attendance.ui.UiState
import com.edge.attendance.ui.components.Glyph
import com.edge.attendance.ui.components.PrimaryButton
import com.edge.attendance.ui.components.QuietButton

@Composable
fun LoginScreen(state: UiState, vm: AttendanceViewModel) {
    var username by rememberSaveable { mutableStateOf(state.lastUsername) }
    var password by rememberSaveable { mutableStateOf("") }
    var portalUrl by rememberSaveable { mutableStateOf(state.portalUrl) }
    var mecUrl by rememberSaveable { mutableStateOf(state.mecUrl) }
    var showServers by rememberSaveable { mutableStateOf(false) }
    val focus = LocalFocusManager.current
    val fieldShape = RoundedCornerShape(12.dp)
    val canSubmit = username.isNotBlank() && password.isNotBlank() && !state.busy
    val hasError = state.message != null // the message itself arrives as a snackbar

    fun submit() {
        if (!canSubmit) return
        focus.clearFocus()
        vm.login(username, password, portalUrl, mecUrl)
        password = ""
    }

    Column(
        Modifier.fillMaxSize().systemBarsPadding().imePadding().verticalScroll(rememberScrollState()).padding(horizontal = 24.dp, vertical = 28.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Glyph(R.drawable.ic_mark, size = 28.dp, tint = MaterialTheme.colorScheme.primary)
            Text("Rollbook", style = MaterialTheme.typography.titleMedium)
        }
        Spacer(Modifier.height(8.dp))
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Sign in", style = MaterialTheme.typography.headlineMedium)
            Text(
                "Take attendance by photographing your class.",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        OutlinedTextField(
            value = username, onValueChange = { username = it }, label = { Text("Username") }, singleLine = true,
            isError = hasError, shape = fieldShape, modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next, keyboardType = KeyboardType.Ascii),
            keyboardActions = KeyboardActions(onNext = { focus.moveFocus(FocusDirection.Down) }),
        )
        OutlinedTextField(
            value = password, onValueChange = { password = it }, label = { Text("Password") }, singleLine = true,
            isError = hasError, shape = fieldShape, modifier = Modifier.fillMaxWidth(),
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
            keyboardActions = KeyboardActions(onDone = { submit() }),
        )
        QuietButton(
            text = if (showServers) "Hide server settings" else "Server settings",
            icon = R.drawable.ic_server, onClick = { showServers = !showServers },
        )
        AnimatedVisibility(showServers) {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = portalUrl, onValueChange = { portalUrl = it }, label = { Text("Portal address") }, singleLine = true,
                    shape = fieldShape, modifier = Modifier.fillMaxWidth(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Next),
                )
                OutlinedTextField(
                    value = mecUrl, onValueChange = { mecUrl = it }, label = { Text("Campus server address") }, singleLine = true,
                    shape = fieldShape, modifier = Modifier.fillMaxWidth(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Done),
                )
            }
        }
        PrimaryButton("Sign in", onClick = ::submit, enabled = canSubmit, loading = state.busy, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(4.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Glyph(R.drawable.ic_lock, size = 18.dp, tint = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(
                "Photos are processed on this phone and are never uploaded.",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
