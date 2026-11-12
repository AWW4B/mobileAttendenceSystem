package com.edge.attendance.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import com.edge.attendance.R
import com.edge.attendance.ui.AttendanceViewModel
import com.edge.attendance.ui.Status
import com.edge.attendance.ui.StudentRow
import com.edge.attendance.ui.UiState
import com.edge.attendance.ui.components.ChipKind
import com.edge.attendance.ui.components.Glyph
import com.edge.attendance.ui.components.GroupHeader
import com.edge.attendance.ui.components.Hairline
import com.edge.attendance.ui.components.PrimaryButton
import com.edge.attendance.ui.components.SecondaryButton
import com.edge.attendance.ui.components.StatusChip
import com.edge.attendance.ui.theme.MonoBody
import com.edge.attendance.ui.theme.StatusBarIcons
import androidx.compose.foundation.isSystemInDarkTheme

private val GROUPS = listOf(
    Status.REVIEW to "Check these",
    Status.ABSENT to "Not seen",
    Status.PRESENT to "Present",
    Status.NOT_ENROLLED to "No face on file",
)

@Composable
fun ReviewScreen(state: UiState, vm: AttendanceViewModel) {
    StatusBarIcons(lightIcons = isSystemInDarkTheme())
    val marked = state.students.count { it.markedPresent }
    val byStatus = state.students.groupBy { it.status }

    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        Row(Modifier.fillMaxWidth().padding(end = 20.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = vm::backToCapture) {
                Glyph(R.drawable.ic_arrow_left, contentDescription = "Back to camera", tint = MaterialTheme.colorScheme.onSurface)
            }
            Text("Review attendance", style = MaterialTheme.typography.titleMedium)
        }
        Column(Modifier.padding(start = 20.dp, end = 20.dp, top = 4.dp, bottom = 12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(marked.toString(), style = MaterialTheme.typography.headlineMedium)
                Text(
                    "of ${state.students.size} marked present", style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(bottom = 3.dp),
                )
            }
            Text(
                "Check the amber rows. Tap a row to correct it.",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        LazyColumn(Modifier.weight(1f).fillMaxWidth()) {
            for ((status, label) in GROUPS) {
                val rows = byStatus[status].orEmpty()
                if (rows.isEmpty()) continue
                item(key = "h-$status") { GroupHeader(label, rows.size) }
                item(key = "t-$status") { Hairline() }
                items(rows, key = StudentRow::pseudonym) { row ->
                    ReviewRow(row) { present -> vm.setPresent(row.pseudonym, present) }
                    Hairline()
                }
            }
        }
        Hairline()
        Row(
            Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.background).navigationBarsPadding()
                .padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            SecondaryButton("More photos", onClick = vm::backToCapture, enabled = !state.busy)
            PrimaryButton("Submit attendance", onClick = vm::submit, loading = state.busy, modifier = Modifier.weight(1f))
        }
    }
}

@Composable
private fun ReviewRow(row: StudentRow, onChange: (Boolean) -> Unit) {
    val enabled = row.status != Status.NOT_ENROLLED
    val (label, kind) = when (row.status) {
        Status.PRESENT -> "Matched ${pct(row.score)}" to ChipKind.Present
        Status.REVIEW -> "Check ${pct(row.score)}" to ChipKind.Review
        Status.ABSENT -> "Not seen" to ChipKind.Neutral
        Status.NOT_ENROLLED -> "No face on file" to ChipKind.Neutral
    }
    Row(
        Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surfaceContainerLowest)
            .toggleable(value = row.markedPresent, enabled = enabled, role = Role.Checkbox, onValueChange = onChange)
            .defaultMinSize(minHeight = 64.dp).padding(start = 8.dp, end = 20.dp, top = 6.dp, bottom = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Checkbox(
            checked = row.markedPresent, onCheckedChange = null, enabled = enabled,
            colors = CheckboxDefaults.colors(checkedColor = MaterialTheme.colorScheme.primary, uncheckedColor = MaterialTheme.colorScheme.outline),
            modifier = Modifier.padding(12.dp),
        )
        Column(Modifier.weight(1f).padding(end = 12.dp)) {
            Text(row.name, style = MaterialTheme.typography.bodyLarge)
            Text(row.rollNo, style = MonoBody, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        StatusChip(label, kind)
    }
}

private fun pct(score: Float?): String = score?.let { "${(it * 100).toInt()}%" }.orEmpty()
