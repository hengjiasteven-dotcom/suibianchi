package com.shiji.app

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.shiji.app.data.CategoryShare
import com.shiji.app.data.TopFood

/** 图表配色：暖底上也能分清，相邻类别不撞色。 */
private val CHART_COLORS = listOf(
    Color(0xFF7FB77E),
    Color(0xFFF2B880),
    Color(0xFF88A9D2),
    Color(0xFFE6A1A1),
    Color(0xFFC7B9E8),
    Color(0xFFF5DA8B),
    Color(0xFF9ED0C6),
    Color(0xFFD9A38B),
    Color(0xFFB5C99A),
    Color(0xFFB0AEBF)
)

fun chartColor(index: Int): Color = CHART_COLORS[index % CHART_COLORS.size]

/** 类别占比环形图：中间写总数，旁边配图例。 */
@Composable
fun CategoryShareChart(shares: List<CategoryShare>, total: Int, modifier: Modifier = Modifier) {
    val sum = shares.sumOf { it.count }.coerceAtLeast(1)
    Row(modifier, verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(132.dp)) {
            Canvas(Modifier.fillMaxSize()) {
                val stroke = size.minDimension * 0.20f
                val inset = stroke / 2f
                val arcSize = Size(size.width - stroke, size.height - stroke)
                var start = -90f
                shares.forEachIndexed { index, share ->
                    val sweep = 360f * share.count / sum
                    drawArc(
                        color = chartColor(index),
                        startAngle = start,
                        sweepAngle = (sweep - 2f).coerceAtLeast(1f),
                        useCenter = false,
                        topLeft = Offset(inset, inset),
                        size = arcSize,
                        style = Stroke(width = stroke, cap = StrokeCap.Butt)
                    )
                    start += sweep
                }
            }
            Column(
                Modifier.align(Alignment.Center),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text("$total", fontSize = 24.sp, fontWeight = FontWeight.Bold)
                Text("条食材", fontSize = 12.sp, color = MaterialTheme.colorScheme.outline)
            }
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            shares.take(7).forEachIndexed { index, share ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        Modifier
                            .size(9.dp)
                            .clip(CircleShape)
                            .background(chartColor(index))
                    )
                    Spacer(Modifier.width(6.dp))
                    Text(
                        share.category,
                        fontSize = 14.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f)
                    )
                    Text("${share.percent}%", fontSize = 14.sp, color = MaterialTheme.colorScheme.outline)
                }
            }
        }
    }
}

/** 最常吃的食材：横向条形图，条长按次数比例。 */
@Composable
fun TopFoodBars(foods: List<TopFood>, modifier: Modifier = Modifier) {
    val max = (foods.maxOfOrNull { it.count } ?: 1).coerceAtLeast(1)
    Column(modifier, verticalArrangement = Arrangement.spacedBy(7.dp)) {
        foods.forEachIndexed { index, food ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    food.name,
                    fontSize = 14.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.width(78.dp)
                )
                Box(
                    Modifier
                        .weight(1f)
                        .height(12.dp)
                        .clip(RoundedCornerShape(6.dp))
                        .background(Color(0x2EFFFFFF))
                ) {
                    Box(
                        Modifier
                            .fillMaxHeight()
                            .fillMaxWidth(food.count.toFloat() / max)
                            .clip(RoundedCornerShape(6.dp))
                            .background(chartColor(index))
                    )
                }
                Text(
                    "${food.count} 次",
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.outline,
                    modifier = Modifier.padding(start = 8.dp)
                )
            }
        }
    }
}
