package com.shiji.app.data

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.graphics.Color
import androidx.compose.material3.Checkbox
import androidx.compose.material3.RadioButton
import androidx.compose.ui.Alignment
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

/** 单选：前面一个圆圈，后面跟选项文字，整块都可点。 */
@Composable
fun ChoiceItem(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Row(
        modifier
            .clip(RoundedCornerShape(8.dp))
            .selectable(selected = selected, onClick = onClick, role = Role.RadioButton)
            .padding(end = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        RadioButton(selected = selected, onClick = null)
        Text(
            label,
            fontSize = 14.sp,
            fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal
        )
    }
}


/** 多选：前面一个方框，后面跟选项文字。 */
@Composable
fun CheckItem(
    label: String,
    checked: Boolean,
    onToggle: () -> Unit,
    modifier: Modifier = Modifier
) {
    Row(
        modifier
            .clip(RoundedCornerShape(8.dp))
            .toggleable(value = checked, onValueChange = { onToggle() }, role = Role.Checkbox)
            .padding(end = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Checkbox(checked = checked, onCheckedChange = null)
        Text(
            label,
            fontSize = 14.sp,
            fontWeight = if (checked) FontWeight.SemiBold else FontWeight.Normal
        )
    }
}


/** 弹窗底色：比原来那层接近不透明的深色淡很多，背后的图能透出来一点。 */
val DialogGlass = Color(0x52101418)

/** 弹窗圆角：跟登录页那张卡片保持一致。 */
private val DialogShape = RoundedCornerShape(20.dp)


/** 通用对话框：标题 + 说明文字 + 可选自定义内容 + 确认/取消。 */


@Composable
fun AlertDialogHost(
    title: String,
    body: String,
    confirmText: String,
    dismissText: String,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
    content: (@Composable () -> Unit)? = null
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        modifier = Modifier.border(1.dp, Color(0x40FFFFFF), DialogShape),
        shape = DialogShape,
        containerColor = DialogGlass,
        title = { Text(title) },
        text = {
            Column {
                if (body.isNotBlank()) {
                    Text(body)
                }
                if (content != null) {
                    if (body.isNotBlank()) {
                        Spacer(Modifier.height(8.dp))
                    }
                    content()
                }
            }
        },
        confirmButton = { TextButton(onClick = onConfirm) { Text(confirmText) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text(dismissText) } }
    )
}
