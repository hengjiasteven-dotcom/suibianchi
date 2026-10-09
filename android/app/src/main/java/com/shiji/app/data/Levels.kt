package com.shiji.app.data

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.roundToInt

/** 忌口三档：不是一上来就"完全不能接受"。 */
val RESTRICTION_LEVELS = listOf(
    1 to "不太喜欢",
    2 to "感觉很难吃",
    3 to "完全不接受"
)

/** 爱好同样是三档。 */
val PREFERENCE_LEVELS = listOf(
    1 to "有点喜欢",
    2 to "很喜欢",
    3 to "最爱吃"
)

fun restrictionLevel(value: Int?): Int = (value ?: 3).coerceIn(1, 3)

fun preferenceLevel(weight: Double?): Int = (weight ?: 2.0).roundToInt().coerceIn(1, 3)

fun restrictionLevelText(value: Int?): String =
    RESTRICTION_LEVELS.firstOrNull { it.first == restrictionLevel(value) }?.second ?: "完全不接受"

fun preferenceLevelText(weight: Double?): String =
    PREFERENCE_LEVELS.firstOrNull { it.first == preferenceLevel(weight) }?.second ?: "很喜欢"


/** 爱好：越爱吃越深（有点喜欢 浅绿 → 最爱吃 深绿）。 */
fun preferenceDotColor(level: Int): Color = when (level.coerceIn(1, 3)) {
    1 -> Color(0xFFA8E0B8)
    2 -> Color(0xFF4FAE7C)
    else -> Color(0xFF1F7A4C)
}


/** 忌口：越不能接受越深（不太喜欢 淡红 → 完全不接受 深红）。 */
fun restrictionDotColor(level: Int): Color = when (level.coerceIn(1, 3)) {
    1 -> Color(0xFFF2BDB8)
    2 -> Color(0xFFD9736D)
    else -> Color(0xFFA3242A)
}


/**
 * 三档程度：浅色圆点 + 档位文字，整块可点。
 * 对话里确认时用它选档，报告里改程度也用它。
 */
@Composable
fun LevelPicker(
    options: List<Pair<Int, String>>,
    selected: Int,
    onSelect: (Int) -> Unit,
    modifier: Modifier = Modifier,
    // 小圆点的颜色按档位走：爱好绿、忌口红，越强就越深
    dotColor: (Int) -> Color = { Color(0xFFE8D9B0) }
) {
    Row(
        modifier,
        horizontalArrangement = Arrangement.spacedBy(5.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        options.forEach { (level, label) ->
            val picked = level == selected
            Row(
                Modifier
                    .clip(RoundedCornerShape(20.dp))
                    .background(if (picked) Color(0x40FFFFFF) else Color(0x14FFFFFF))
                    .border(
                        1.dp,
                        if (picked) Color(0x99FFFFFF) else Color(0x26FFFFFF),
                        RoundedCornerShape(20.dp)
                    )
                    .clickable { onSelect(level) }
                    .padding(horizontal = 6.dp, vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    Modifier
                        .size(if (picked) 9.dp else 7.dp)
                        .clip(CircleShape)
                        .background(dotColor(level))
                )
                Text(
                    label,
                    fontSize = 13.sp,
                    maxLines = 1,
                    softWrap = false,
                    fontWeight = if (picked) FontWeight.SemiBold else FontWeight.Normal,
                    color = if (picked) Color.White else Color(0xCCFFFFFF),
                    modifier = Modifier.padding(start = 5.dp)
                )
            }
        }
    }
}
