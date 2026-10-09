package com.shiji.app.data

import android.content.Context
import android.content.SharedPreferences

/**
 * 本机登录状态。
 * - access：访问令牌，给接口用（重启后会重新换一张，不长期依赖）
 * - device：设备令牌，用来免验证码快速登录；只有主动退出登录 / 注销才会清掉
 * - phone：登录过的手机号，退出后还能在登录页带出来
 */
object TokenStore {
    private const val FILE = "shiji_auth"
    private const val KEY_ACCESS = "access_token"
    private const val KEY_DEVICE = "device_token"
    private const val KEY_PHONE = "phone"

    private var prefs: SharedPreferences? = null

    fun init(context: Context) {
        if (prefs == null) {
            prefs = context.applicationContext.getSharedPreferences(FILE, Context.MODE_PRIVATE)
        }
        // 内存里的令牌先恢复，免得冷启动第一次请求没带上头
        ApiClient.token = prefs?.getString(KEY_ACCESS, null)
    }

    val deviceToken: String?
        get() = prefs?.getString(KEY_DEVICE, null)

    val phone: String?
        get() = prefs?.getString(KEY_PHONE, null)

    /** 登录成功后落盘：设备令牌给了就一起记住。 */
    fun saveLogin(access: String?, device: String?, phone: String?) {
        prefs?.edit()?.apply {
            if (access != null) putString(KEY_ACCESS, access)
            if (device != null) putString(KEY_DEVICE, device)
            if (phone != null) putString(KEY_PHONE, phone)
        }?.apply()
        if (access != null) ApiClient.token = access
    }

    /** 主动退出登录 / 注销账号：设备令牌一并清掉，下次要重新验证码。 */
    fun clear() {
        prefs?.edit()?.clear()?.apply()
        ApiClient.token = null
    }
}
