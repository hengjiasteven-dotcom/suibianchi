# 随便吃服务端

FastAPI + SQLite 实现，覆盖需求规格 v0.2 的主链路。

## 快速开始

```bash
cd server
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- 接口文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

首次启动会自动建库，并把 `output/heat_index/app/app_heat_index.jsonl`（1198 条热量数据）导入 SQLite。

## 自测

```bash
cd server
python tests/test_flow.py
```

覆盖：注册登录 → 设备免验证码登录 → 密码登录 → 档案与忌口 → 热量检索 → 识别 → 确认入库 → 记录查询 → 推荐（含忌口硬约束）→ 外卖店铺 → 对话（含忌口确认）→ 周报告 → 分享。

## 接口一览

| 分组 | 路径 |
| --- | --- |
| 认证 | `POST /api/v1/auth/sms/send`、`/sms/verify`、`/login/password`、`/device/login`、`/password/reset`、`DELETE /api/v1/account` |
| 档案 | `GET/PUT /api/v1/profile`、`GET/POST /api/v1/profile/restrictions`、`PATCH .../restrictions/{id}`、`GET/POST /api/v1/profile/preferences` |
| 记录 | `POST/GET /api/v1/meals`、`GET/PATCH /api/v1/meals/{id}`、`POST /api/v1/meals/{id}/photos` |
| 识别 | `POST /api/v1/recognition`、`POST /api/v1/recognition/{job_id}/confirm` |
| 热量 | `GET /api/v1/foods/search?q=` |
| 推荐 | `POST /api/v1/recommendations`、`GET /api/v1/stores/nearby` |
| 对话 | `POST /api/v1/chat/sessions`、`POST .../{sid}/messages`、`POST .../{sid}/end` |
| 报告 | `GET /api/v1/reports?period=3d\|week\|month\|quarter` |
| 分享 | `POST /api/v1/shares`、`GET /api/v1/shares/{id}` |

## 开发模式与生产切换

当前默认全部走本地实现，配置对应环境变量即可切到真实服务：

| 能力 | 环境变量 | 说明 |
| --- | --- | --- |
| 短信 | `SHIJI_SMS_DEV_MODE=0` | 为 0 时需要接入短信服务商 SDK；开发模式会直接返回验证码 |
| AI | `DEEPSEEK_API_KEY` | 配置后自动启用 DeepSeek（`deepseek-flash`）做识别、推荐、对话；未配置时用本地规则引擎 |
| 图片存储 | `QINIU_ACCESS_KEY`、`QINIU_SECRET_KEY`、`QINIU_BUCKET` | 未配置时返回 mock 上传凭证 |
| 地图 | `BAIDU_MAP_AK` | 未配置时返回示例店铺 |
| 数据库 | `SHIJI_DB_PATH` | 默认 `server/data/shiji.db`，可换成 PostgreSQL 时替换 `app/db.py` |

## 已实现的关键规则

- 忌口/过敏为硬约束，推荐结果不会出现；对话抽取到的忌口必须用户确认后才生效
- 对话原文不落库，会话只存在进程内存并带 10 分钟 TTL，结束后立即清空
- 记录无删除入口，只支持编辑；补录最多回溯 2 天
- 热量由 AI 按食材逐项估算（每种食材给出克数、每百克热量、这一份热量），服务端校验后用「克数 × 每百克 ÷ 100」重算并汇总，保证明细与合计一致
- 本地 1211 条索引不再参与主流程；如需让 AI 参考它，设 `SHIJI_AI_INCLUDE_INDEX=1` 即可把索引作为提示词前缀
- 图片以 base64（裸 base64 或完整 data URL）传给 `/api/v1/recognition` 的 `images_base64` 字段，服务端自动识别 PNG/JPEG/GIF/WebP 后转给 DeepSeek
- 分享内容不含照片、时间、地点等隐私字段
- 账号注销与个人数据删除提供合规通道 `DELETE /api/v1/account`
