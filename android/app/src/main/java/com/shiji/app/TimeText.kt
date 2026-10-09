package com.shiji.app

import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * 服务端统一存 UTC 时间（形如 2026-10-08T10:22:47.198142+00:00）。
 * 这里统一转成本机时区再展示，避免出现"凌晨吃的东西算到前一天"。
 */

private fun parseIso(iso: String): Date? = try {
    val value = iso.trim()
    val normalized = if (value.length >= 19) value.take(19) else value
    SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).apply {
        timeZone = TimeZone.getTimeZone("UTC")
    }.parse(normalized)
} catch (e: Exception) {
    null
}

private fun format(pattern: String, locale: Locale, date: Date): String =
    SimpleDateFormat(pattern, locale).format(date)

/** 本机日期（yyyy-MM-dd）：告诉服务端这条记录算哪一天。 */
fun localDateFor(daysAgo: Int): String {
    val calendar = Calendar.getInstance()
    calendar.add(Calendar.DAY_OF_YEAR, -daysAgo)
    return format("yyyy-MM-dd", Locale.US, calendar.time)
}


/** 本机时区下的日期 key，用于按天分组。 */
fun localDateKey(iso: String): String {
    val date = parseIso(iso) ?: return iso.take(10)
    return format("yyyy-MM-dd", Locale.US, date)
}

/** 日期 key（yyyy-MM-dd）→「10月5日 周一」，给按天详情用。 */
fun friendlyDayTitle(dateKey: String): String {
    val date = try {
        SimpleDateFormat("yyyy-MM-dd", Locale.US).parse(dateKey)
    } catch (e: Exception) {
        null
    } ?: return dateKey
    return format("M月d日", Locale.CHINA, date) + " " + format("EEE", Locale.CHINA, date)
}


/** 本机时区下的时间，形如 12:30。 */
fun localClock(iso: String): String {
    val date = parseIso(iso) ?: return iso.drop(11).take(5)
    return format("HH:mm", Locale.US, date)
}

/** 广场、分享列表用的短时间：本机时区 MM-dd HH:mm。 */
fun localShortDateTime(iso: String): String {
    val date = parseIso(iso) ?: return iso.take(16).replace("T", " ")
    return format("MM-dd HH:mm", Locale.US, date)
}

/** 本机时区下的日期 + 时间，形如「今天 12:30」。 */
fun friendlyDateTime(iso: String): String {
    val date = parseIso(iso) ?: return iso.take(16).replace("T", " ")
    val key = format("yyyy-MM-dd", Locale.US, date)
    val calendar = Calendar.getInstance()
    val today = format("yyyy-MM-dd", Locale.US, calendar.time)
    calendar.add(Calendar.DAY_OF_YEAR, -1)
    val yesterday = format("yyyy-MM-dd", Locale.US, calendar.time)
    val day = when (key) {
        today -> "今天"
        yesterday -> "昨天"
        else -> format("M月d日", Locale.CHINA, date)
    }
    return "$day ${format("HH:mm", Locale.US, date)}"
}
