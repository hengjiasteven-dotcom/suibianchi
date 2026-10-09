package com.shiji.app

import androidx.compose.material3.Typography
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight

/**
 * 全站字体：腾祥小小新体简。
 * 同一个 ttf 登记到几个常用字重上，粗体、半粗也走这套字形，不会回退成系统字体。
 */
val AppFontFamily = FontFamily(
    Font(R.font.tengxiang_xiaoxiao, FontWeight.Normal),
    Font(R.font.tengxiang_xiaoxiao, FontWeight.Medium),
    Font(R.font.tengxiang_xiaoxiao, FontWeight.SemiBold),
    Font(R.font.tengxiang_xiaoxiao, FontWeight.Bold)
)

/** 把 Material 的 15 个文字样式全部换成这套字体：Text 不写 fontFamily 也生效。 */
val AppTypography: Typography = Typography().let { base ->
    base.copy(
        displayLarge = base.displayLarge.copy(fontFamily = AppFontFamily),
        displayMedium = base.displayMedium.copy(fontFamily = AppFontFamily),
        displaySmall = base.displaySmall.copy(fontFamily = AppFontFamily),
        headlineLarge = base.headlineLarge.copy(fontFamily = AppFontFamily),
        headlineMedium = base.headlineMedium.copy(fontFamily = AppFontFamily),
        headlineSmall = base.headlineSmall.copy(fontFamily = AppFontFamily),
        titleLarge = base.titleLarge.copy(fontFamily = AppFontFamily),
        titleMedium = base.titleMedium.copy(fontFamily = AppFontFamily),
        titleSmall = base.titleSmall.copy(fontFamily = AppFontFamily),
        bodyLarge = base.bodyLarge.copy(fontFamily = AppFontFamily),
        bodyMedium = base.bodyMedium.copy(fontFamily = AppFontFamily),
        bodySmall = base.bodySmall.copy(fontFamily = AppFontFamily),
        labelLarge = base.labelLarge.copy(fontFamily = AppFontFamily),
        labelMedium = base.labelMedium.copy(fontFamily = AppFontFamily),
        labelSmall = base.labelSmall.copy(fontFamily = AppFontFamily)
    )
}
