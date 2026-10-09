# 随便吃 Android 端

Kotlin + Jetpack Compose，调用 `server/` 里的 FastAPI 接口。

## 环境（本机已配置好）

| 组件 | 位置 | 版本 |
| --- | --- | --- |
| JDK | `C:\android-dev\jdk\jdk-17.0.20.1+1` | Temurin 17.0.20.1 |
| Android SDK | `C:\android-dev\sdk` | platform 34、build-tools 34.0.0、platform-tools |
| Gradle | `C:\android-dev\gradle\gradle-8.7` | 8.7（工程内已带 wrapper） |

用户级环境变量已写入：`JAVA_HOME`、`ANDROID_HOME`、`ANDROID_SDK_ROOT`，并把 Gradle 与 platform-tools 加进了 `Path`。新开终端即可生效。

## 编译

```bash
cd android
gradlew.bat assembleDebug
```

产物：`android\app\build\outputs\apk\debug\app-debug.apk`（约 15.5 MB）

安装到已连接的设备或模拟器：

```bash
adb install -r app\build\outputs\apk\debug\app-debug.apk
```

## 服务端地址

`app/src/main/java/com/shiji/app/data/Api.kt` 里的 `ApiClient.baseUrl`：

- 模拟器：`http://10.0.2.2:8000/`（默认，指向宿主机的 8000 端口）
- 真机：改成电脑在局域网里的 IP，例如 `http://192.168.1.10:8000/`，并确保手机和电脑同一网段

开发期已通过 `network_security_config.xml` 允许明文 HTTP，上线前要改成仅 HTTPS。

## 已实现的页面

## 模拟器验证记录

已在 Android 模拟器（emulator-5554）上完成真实安装与端到端验证：

1. 手机号 13900001111 → 取验证码（服务端开发模式回显 506176）→ 设密码 → 登录成功
2. 记录一餐：输入「米饭和鲈鱼」→ 识别弹窗显示「米饭（约 118 kcal）、鲈鱼（约 105 kcal）」→ 确认后首页显示「午餐 / 米饭、鲈鱼 / 约 223 kcal（估算）」
3. 推荐页：下厨场景输出 3 套方案，并提示「需要补充蔬菜类、水果类、乳类」
4. 报告页：最近 7 天 2 条食材记录，谷类 50%、鱼虾蟹贝类 50%，并列出缺口

自动化注意：该模拟器把应用跑在副显示器上，使用 adb 注入事件时要加 `-d 3`，例如 `adb shell input -d 3 tap x y`，否则点击无效。

- 登录 / 注册：手机号 + 验证码，首次设置密码（服务端开发模式会直接把验证码回显出来）
- 今天：三餐记录列表、每餐热量合计、记录一餐入口
- 记录一餐：填写吃了什么 → 调识别接口 → 弹确认框（可看到每个食材的热量）→ 确认入库
- 推荐：自己做 / 点外卖两种场景，输出 3 套方案，外卖场景附附近店铺
- 报告：周维度食物类别占比与缺口提醒
- 我的：膳食目标多选、忌口录入、生成一周分享

## 与需求文档的对应关系

- 三餐固定槽位，未记录留空
- 记录只能编辑、不提供删除；补录限制在两天内（服务端校验）
- 忌口是硬约束，推荐结果不会出现
- 热量一律来自本地索引，界面上标注“估算”
- 分享不含照片与时间地点

## 已知待补

- App 图标尚未替换，用的系统默认图标
- 拍照/相册选图还没接（当前记录以文字输入为主，识别接口已支持传图片 key）
- 历史记录的日历视图、拖动补录交互未实现
- 对话式推荐页未接进 UI（服务端接口已就绪）
