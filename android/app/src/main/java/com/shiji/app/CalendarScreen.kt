package com.shiji.app

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.calculateZoom
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.shiji.app.data.Meal
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale

/** 早/中/晚三行固定，横向按天 / 周 / 月滑动，像课表一样。 */
val SLOTS = listOf("breakfast" to "早", "lunch" to "午", "dinner" to "晚", "supper" to "宵")
private const val CENTER_PAGE = 120

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun CalendarScreen(
    meals: List<Meal>,
    busy: Boolean,
    onRefresh: () -> Unit,
    onDayClick: (date: String) -> Unit,
    onCellClick: (date: String, slot: String) -> Unit
) {
    var mode by remember { mutableStateOf(1) } // 0 日 / 1 周 / 2 月
    val today = remember {
        Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
    }
    // 服务端存的是 UTC，按本机时区换算日期再分组
    val mealMap = remember(meals) {
        meals.groupBy { localDateKey(it.eaten_at) + "|" + it.meal_slot }
    }
    val pagerState = rememberPagerState(initialPage = CENTER_PAGE, pageCount = { CENTER_PAGE * 2 + 1 })
    val scope = rememberCoroutineScope()

    // 周视图里点日期→日视图，点月份→月视图；同一个 pager 直接翻到对应页
    fun openDay(day: Calendar) {
        val page = (CENTER_PAGE + daysBetween(today, day)).coerceIn(0, CENTER_PAGE * 2)
        scope.launch { pagerState.scrollToPage(page) }
        mode = 0
    }

    fun openMonth(anyDayInMonth: Calendar) {
        val page = (CENTER_PAGE + monthsBetween(today, anyDayInMonth)).coerceIn(0, CENTER_PAGE * 2)
        scope.launch { pagerState.scrollToPage(page) }
        mode = 2
    }

    // 月视图里点月份 → 回到那一周的周视图
    fun openWeek(anyDayInMonth: Calendar) {
        val mondayBased = (today.get(Calendar.DAY_OF_WEEK) + 5) % 7
        val offset = Math.floorDiv(
            daysBetween(today, anyDayInMonth) + mondayBased,
            7
        )
        val page = (CENTER_PAGE + offset).coerceIn(0, CENTER_PAGE * 2)
        scope.launch { pagerState.scrollToPage(page) }
        mode = 1
    }

    Column(
        Modifier
            .fillMaxSize()
            .padding(12.dp)
            // 双指一收：日 → 周 → 月；双指一张再退回来
            .pinchZoom(
                onZoomOut = { if (mode < 2) mode += 1 },
                onZoomIn = { if (mode > 0) mode -= 1 }
            )
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(
                "点格子看详情，双指一缩看整月",
                fontSize = 14.sp,
                color = MaterialTheme.colorScheme.outline,
                modifier = Modifier.weight(1f)
            )
            TextButton(onClick = onRefresh, enabled = !busy) { Text("刷新", fontSize = 14.sp) }
        }
        Spacer(Modifier.height(2.dp))

        when (mode) {
            0 -> DayPager(pagerState, today, mealMap, onCellClick)
            1 -> WeekPager(
                pagerState = pagerState,
                today = today,
                mealMap = mealMap,
                onCellClick = onCellClick,
                onOpenDay = { openDay(it) },
                onOpenMonth = { openMonth(it) },
            )
            else -> MonthPager(
                pagerState = pagerState,
                today = today,
                mealMap = mealMap,
                onDayClick = onDayClick,
                onOpenWeek = { openWeek(it) }
            )
        }
    }
}



/** 双指缩放：只在真的双指缩放时消费手势，单指左右滑仍然交给 Pager。 */
private fun Modifier.pinchZoom(onZoomOut: () -> Unit, onZoomIn: () -> Unit): Modifier =
    this.pointerInput(Unit) {
        awaitEachGesture {
            awaitFirstDown(requireUnconsumed = false)
            var scale = 1f
            var taken = false
            while (true) {
                val event = awaitPointerEvent()
                if (event.changes.none { it.pressed }) break
                if (event.changes.count { it.pressed } >= 2) {
                    val zoom = event.calculateZoom()
                    if (zoom != 1f) {
                        scale *= zoom
                        if (!taken) {
                            taken = true
                            event.changes.forEach { it.consume() }
                        }
                    }
                }
            }
            if (taken) {
                if (scale < 0.85f) onZoomOut() else if (scale > 1.18f) onZoomIn()
            }
        }
    }


/* ------------------------------------------------ 周视图 ------------------------------------------------ */

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun WeekPager(
    pagerState: androidx.compose.foundation.pager.PagerState,
    today: Calendar,
    mealMap: Map<String, List<Meal>>,
    onCellClick: (String, String) -> Unit,
    onOpenDay: (Calendar) -> Unit,
    onOpenMonth: (Calendar) -> Unit
) {
    HorizontalPager(state = pagerState) { page ->
        val weekStart = weekStart(today, page - CENTER_PAGE)
        val days = (0 until 7).map { offset ->
            (weekStart.clone() as Calendar).apply { add(Calendar.DAY_OF_MONTH, offset) }
        }
        // 周标题按这一周的周四所在的月份写，跨月的周不会显示成上个月
        val weekMonth = (weekStart.clone() as Calendar).apply { add(Calendar.DAY_OF_MONTH, 3) }
        // 表头固定，剩下高度四等分给早/午/晚/宵：一屏就能看完，不用上下滑
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val rowHeight = ((maxHeight - 106.dp) / 4).coerceAtLeast(54.dp)
            Column(Modifier.fillMaxSize()) {
            // 月份：点一下进月视图
            Text(
                SimpleDateFormat("yyyy 年 M 月", Locale.CHINA).format(weekMonth.time) + " ⌄",
                fontSize = 15.sp,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier
                    .clip(RoundedCornerShape(20.dp))
                    .clickable { onOpenMonth(weekMonth) }
                    .padding(horizontal = 8.dp, vertical = 2.dp)
            )
            Spacer(Modifier.height(2.dp))
            Row(Modifier.fillMaxWidth()) {
                Box(Modifier.width(28.dp))
                days.forEach { day ->
                    // 日期：点一下进日视图
                    Column(
                        Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(8.dp))
                            .clickable { onOpenDay(day) }
                            .padding(vertical = 2.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            SimpleDateFormat("d", Locale.CHINA).format(day.time),
                            fontSize = 14.sp,
                            fontWeight = if (isSameDay(day, today)) FontWeight.Bold else FontWeight.Normal
                        )
                        Text(weekdayLabel(day).removePrefix("周"), fontSize = 12.sp, color = MaterialTheme.colorScheme.outline)
                    }
                }
            }
            Spacer(Modifier.height(2.dp))
            SLOTS.forEach { (slot, slotLabel) ->
                Row(Modifier.fillMaxWidth().height(rowHeight)) {
                    Box(Modifier.width(28.dp).fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text(slotLabel, fontWeight = FontWeight.Bold)
                    }
                    days.forEach { day ->
                        MealCell(
                            date = dateKey(day),
                            slot = slot,
                            meals = mealMap["${dateKey(day)}|$slot"].orEmpty(),
                            isToday = isSameDay(day, today),
                            modifier = Modifier.weight(1f),
                            energyOnly = true,
                            onClick = onCellClick
                        )
                    }
                }
            }
            }
        }
    }
}

/* ------------------------------------------------ 日视图 ------------------------------------------------ */

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun DayPager(
    pagerState: androidx.compose.foundation.pager.PagerState,
    today: Calendar,
    mealMap: Map<String, List<Meal>>,
    onCellClick: (String, String) -> Unit
) {
    HorizontalPager(state = pagerState) { page ->
        val day = (today.clone() as Calendar).apply { add(Calendar.DAY_OF_MONTH, page - CENTER_PAGE) }
        val key = dateKey(day)
        // 标题之外的高度四等分：早/午/晚/宵一屏全部看得到，不用滑动
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val rowHeight = ((maxHeight - 58.dp) / 4).coerceAtLeast(76.dp)
            Column(Modifier.fillMaxSize()) {
            Text(
                SimpleDateFormat("yyyy 年 M 月 d 日", Locale.CHINA).format(day.time) + "  " + weekdayLabel(day),
                fontWeight = FontWeight.Bold
            )
            Spacer(Modifier.height(6.dp))
            SLOTS.forEach { (slot, label) ->
                Row(Modifier.fillMaxWidth().height(rowHeight)) {
                    Box(Modifier.width(40.dp).fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text(label, fontWeight = FontWeight.Bold, fontSize = 20.sp)
                    }
                    MealCell(
                        date = key,
                        slot = slot,
                        meals = mealMap["$key|$slot"].orEmpty(),
                        isToday = isSameDay(day, today),
                        modifier = Modifier.weight(1f),
                        onClick = onCellClick,
                        big = true
                    )
                }
            }
            }
        }
    }
}

/* ------------------------------------------------ 月视图 ------------------------------------------------ */

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun MonthPager(
    pagerState: androidx.compose.foundation.pager.PagerState,
    today: Calendar,
    mealMap: Map<String, List<Meal>>,
    onDayClick: (String) -> Unit,
    onOpenWeek: (Calendar) -> Unit
) {
    HorizontalPager(state = pagerState) { page ->
        val first = (today.clone() as Calendar).apply {
            add(Calendar.MONTH, page - CENTER_PAGE)
            set(Calendar.DAY_OF_MONTH, 1)
        }
        val leading = (first.get(Calendar.DAY_OF_WEEK) + 5) % 7 // 周一为第一列
        val daysInMonth = first.getActualMaximum(Calendar.DAY_OF_MONTH)
        val rows = (leading + daysInMonth + 6) / 7
        // 正规日历的样子：标题 + 星期行固定，剩下按行数均分，一屏正好一整个月
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val cellHeight = ((maxHeight - 52.dp) / rows).coerceAtLeast(46.dp)
            Column(Modifier.fillMaxSize()) {
            // 月份：点一下回周视图
            Text(
                SimpleDateFormat("yyyy 年 M 月", Locale.CHINA).format(first.time) + " ⌃",
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .clip(RoundedCornerShape(20.dp))
                    .clickable { onOpenWeek(first) }
                    .padding(horizontal = 8.dp, vertical = 2.dp)
            )
            Spacer(Modifier.height(6.dp))
            Row(Modifier.fillMaxWidth()) {
                listOf("一", "二", "三", "四", "五", "六", "日").forEachIndexed { index, label ->
                    Text(
                        label,
                        Modifier.weight(1f),
                        fontSize = 13.sp,
                        color = if (index >= 5) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center
                    )
                }
            }
            Spacer(Modifier.height(4.dp))
            for (r in 0 until rows) {
                Row(Modifier.fillMaxWidth().height(cellHeight)) {
                    for (c in 0 until 7) {
                        val dayNum = r * 7 + c - leading + 1
                        if (dayNum in 1..daysInMonth) {
                            val day = (first.clone() as Calendar).apply { set(Calendar.DAY_OF_MONTH, dayNum) }
                            val key = dateKey(day)
                            val filled = SLOTS.count { mealMap.containsKey("$key|${it.first}") }
                            val holiday = holidayOf(day)
                            val isTodayCell = isSameDay(day, today)
                            // 整格可点：点某天以该天的午餐为入口
                            Column(
                                Modifier
                                    .weight(1f)
                                    .padding(1.dp)
                                    .clip(RoundedCornerShape(7.dp))
                                    .background(
                                        when {
                                            isTodayCell -> MaterialTheme.colorScheme.primaryContainer
                                            c >= 5 -> Color(0x2EFFFFFF)
                                            else -> MaterialTheme.colorScheme.surfaceVariant
                                        }
                                    )
                                    .clickable { onDayClick(key) }
                                    .padding(horizontal = 2.dp, vertical = 3.dp),
                                horizontalAlignment = Alignment.CenterHorizontally
                            ) {
                                Text(
                                    "$dayNum",
                                    fontSize = 15.sp,
                                    fontWeight = if (isTodayCell) FontWeight.Bold else FontWeight.Normal
                                )
                                // 节日用一行小字标在日期下面
                                if (holiday != null) {
                                    Text(
                                        holiday,
                                        fontSize = 11.sp,
                                        color = Color(0xFFE8D9B0),
                                        maxLines = 1
                                    )
                                }
                                if (filled > 0) {
                                    Text(
                                        "$filled 餐",
                                        fontSize = 11.sp,
                                        color = MaterialTheme.colorScheme.primary,
                                        maxLines = 1
                                    )
                                }
                            }
                        } else {
                            Box(Modifier.weight(1f))
                        }
                    }
                }
            }
        }
    }
}

}

/* ------------------------------------------------ 单元格 ------------------------------------------------ */

@Composable
private fun MealCell(
    date: String,
    slot: String,
    meals: List<Meal>,
    isToday: Boolean,
    modifier: Modifier = Modifier,
    big: Boolean = false,
    energyOnly: Boolean = false,
    onClick: (String, String) -> Unit
) {
    // 有菜品名就先显示菜品，不然一格子全是食材太碎
    val dishes = meals.flatMap { it.items }
        .mapNotNull { it.dish_name?.trim()?.takeIf { name -> name.isNotBlank() } }
        .distinct()
    val names = if (dishes.isNotEmpty()) dishes.joinToString("、")
    else meals.flatMap { it.items }.joinToString("、") { it.food_name }
    // 课表格子很窄，只显示前两样 + “等”，详情点进日视图看
    val itemNames = if (dishes.isNotEmpty()) dishes else meals.flatMap { it.items }.map { it.food_name }
    val compactNames = if (itemNames.size <= 2) itemNames.joinToString("、")
    else itemNames.take(2).joinToString("、") + "等"
    val total = meals.sumOf { it.total_energy_kcal }
    // 周视图格子窄，只放第一样，写不下就省略号
    val firstName = itemNames.firstOrNull().orEmpty()
    // 有记录：米黄色半透明块；未记录：几乎透明，不留黑面板
    val filled = meals.isNotEmpty()
    val panelColor = when {
        filled -> Color(0x7AE8D9B0)
        isToday -> Color(0x24FFFFFF)
        else -> Color(0x26FFFFFF)
    }
    val contentColor = if (filled) Color(0xFF2A2114) else Color(0xCCFFFFFF)
    Box(
        modifier
            .padding(1.dp)
            .background(
                panelColor,
                RoundedCornerShape(6.dp)
            )
            .clickable { onClick(date, slot) }
            .padding(if (big) 6.dp else 3.dp)
    ) {
        if (meals.isEmpty()) {
            // 周视图对应的就是一个餐次：没记录就留空，只留淡底（点一下还能补录）
            if (!energyOnly) {
                Text("未记录", fontSize = if (big) 12.sp else 9.sp, color = contentColor)
            }
        } else if (energyOnly) {
            // 周视图：餐名在上、能量在下
            Column(
                Modifier.fillMaxSize().padding(top = 2.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Top
            ) {
                if (meals.any { it.status == "estimating" }) {
                    Text("估算中", fontSize = 11.sp, color = contentColor)
                } else {
                    Text(
                        firstName,
                        fontSize = 11.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        color = contentColor
                    )
                    Text(
                        "${total.toInt()}",
                        fontSize = if (big) 15.sp else 11.sp,
                        fontWeight = FontWeight.Medium,
                        color = contentColor
                    )
                    Text(
                        "kcal",
                        fontSize = if (big) 9.sp else 8.sp,
                        color = contentColor.copy(alpha = 0.7f)
                    )
                }
            }
        } else {
            Column {
                Text(
                    if (big) names else compactNames,
                    fontSize = if (big) 14.sp else 9.sp,
                    maxLines = if (big) 3 else 2,
                    overflow = TextOverflow.Ellipsis,
                    color = contentColor
                )
                Text(
                    if (meals.any { it.status == "estimating" }) "热量估算中…"
                    else if (meals.size > 1) "${meals.size}条·${total.toInt()}"
                    else "${total.toInt()} kcal",
                    fontSize = if (big) 12.sp else 10.sp,
                    color = contentColor.copy(alpha = 0.75f)
                )
                if (big) {
                    val note = meals.firstOrNull { it.note.isNotBlank() }?.note
                    if (!note.isNullOrBlank()) {
                        Text("备注：$note", fontSize = 13.sp, color = contentColor.copy(alpha = 0.7f))
                    }
                }
            }
        }
    }
}

/* ------------------------------------------------ 节日 ------------------------------------------------ */

/** 农历节日算出来的公历日期，按年缓存。 */
private val lunarHolidayCache = mutableMapOf<Int, Map<String, String>>()

private fun lunarHolidaysOf(year: Int): Map<String, String> = lunarHolidayCache.getOrPut(year) {
    val out = mutableMapOf<String, String>()
    // 腊月/正月会跨到次年一月，所以从元旦往后扫 400 天
    val targets = mapOf(
        (1 to 1) to "春节",
        (5 to 5) to "端午",
        (8 to 15) to "中秋"
    )
    runCatching {
        val cc = android.icu.util.ChineseCalendar()
        cc.timeZone = android.icu.util.TimeZone.getDefault()
        val gregorian = Calendar.getInstance().apply {
            set(year, Calendar.JANUARY, 1, 12, 0, 0)
            set(Calendar.MILLISECOND, 0)
        }
        repeat(400) {
            cc.timeInMillis = gregorian.timeInMillis
            val leap = cc.get(android.icu.util.ChineseCalendar.IS_LEAP_MONTH)
            val month = cc.get(android.icu.util.ChineseCalendar.MONTH) + 1
            val day = cc.get(android.icu.util.ChineseCalendar.DAY_OF_MONTH)
            if (leap == 0) {
                targets[month to day]?.let { name -> out[dateKey(gregorian)] = name }
            }
            gregorian.add(Calendar.DAY_OF_MONTH, 1)
        }
    }
    out
}


/** 清明按节气算，用常用近似公式就够（2000-2099 有效）。 */
private fun qingmingDay(year: Int): Int {
    val y = year % 100
    return (y * 0.2422 + 4.81).toInt() - y / 4
}


/** 这一天是什么节日；没有节日就返回 null。 */
private fun holidayOf(day: Calendar): String? {
    val month = day.get(Calendar.MONTH) + 1
    val date = day.get(Calendar.DAY_OF_MONTH)
    val year = day.get(Calendar.YEAR)
    when {
        month == 1 && date == 1 -> return "元旦"
        month == 4 && date == qingmingDay(year) -> return "清明"
        month == 5 && date == 1 -> return "劳动节"
        month == 10 && date == 1 -> return "国庆"
    }
    return lunarHolidaysOf(year)[dateKey(day)]
}


/* ------------------------------------------------ 日期工具 ------------------------------------------------ */

private fun dateKey(cal: Calendar): String =
    SimpleDateFormat("yyyy-MM-dd", Locale.US).format(cal.time)

private fun isSameDay(a: Calendar, b: Calendar): Boolean =
    a.get(Calendar.YEAR) == b.get(Calendar.YEAR) &&
        a.get(Calendar.DAY_OF_YEAR) == b.get(Calendar.DAY_OF_YEAR)

private fun weekdayLabel(cal: Calendar): String =
    listOf("周日", "周一", "周二", "周三", "周四", "周五", "周六")[cal.get(Calendar.DAY_OF_WEEK) - 1]

/** 以周一为一周第一天。 */
private fun weekStart(today: Calendar, weekOffset: Int): Calendar {
    val cal = today.clone() as Calendar
    val delta = (cal.get(Calendar.DAY_OF_WEEK) + 5) % 7
    cal.add(Calendar.DAY_OF_MONTH, -delta + weekOffset * 7)
    return cal
}

/** 两个日期差多少天（按当天零点算，防止夏令时/时分干扰）。 */
private fun daysBetween(from: Calendar, to: Calendar): Int {
    val a = (from.clone() as Calendar).apply {
        set(Calendar.HOUR_OF_DAY, 0); set(Calendar.MINUTE, 0)
        set(Calendar.SECOND, 0); set(Calendar.MILLISECOND, 0)
    }
    val b = (to.clone() as Calendar).apply {
        set(Calendar.HOUR_OF_DAY, 0); set(Calendar.MINUTE, 0)
        set(Calendar.SECOND, 0); set(Calendar.MILLISECOND, 0)
    }
    return ((b.timeInMillis - a.timeInMillis) / (24L * 3600 * 1000)).toInt()
}


/** 两个日期差多少个月，用于翻到对应月。 */
private fun monthsBetween(from: Calendar, to: Calendar): Int =
    (to.get(Calendar.YEAR) - from.get(Calendar.YEAR)) * 12 +
        (to.get(Calendar.MONTH) - from.get(Calendar.MONTH))


/** 计算某个日期距今天几天，用于判断能否补录。 */
fun daysAgoOf(date: String): Int? {
    return try {
        val fmt = SimpleDateFormat("yyyy-MM-dd", Locale.US)
        val target = fmt.parse(date) ?: return null
        val today = Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        ((today.timeInMillis - target.time) / (24L * 3600 * 1000)).toInt()
    } catch (e: Exception) {
        null
    }
}
