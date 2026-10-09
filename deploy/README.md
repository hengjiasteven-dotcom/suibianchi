# 随便吃 · 服务端部署说明

## 架构（现在的方案）

```
手机 App ──HTTPS──▶ api.xiaodaidai.site（Nginx 反代）
                          │
                          └──▶ uvicorn + FastAPI（127.0.0.1:8010，systemd 常驻）
                                  ├── SQLite（用户/记录/忌口爱好/分类缓存）  ← 用户数据存这里
                                  ├── DeepSeek API（识图 / 估算 / 对话 / 分类，走外网）
                                  └── 百度地图 API（附近真店铺，走外网）

照片 ──▶ 七牛云（eating.xiaodaidai.site，静态图片域名）
```

- 网站（xiaodaidai.site）和 App 后端互不影响：后端只占一个端口 + 一点内存。
- 图片不进服务器磁盘，走七牛云；服务器只存文字数据。

## 这台服务器够不够用

| 项目 | 实际占用 |
| --- | --- |
| 内存 | uvicorn 常驻约 80–150 MB |
| CPU | 平时几乎为 0；只有处理请求时用一点，AI 推理在 DeepSeek 那边 |
| 磁盘 | 数据库现在 1.5 MB；1 万条饮食记录约几十 MB；备份每天一份、保留 14 天 |
| 带宽 | 只传文字（照片直接传七牛），单次请求几 KB |

结论：**只要服务器还剩 300 MB 可用内存、能开一个额外端口，就完全够用。**
真正花钱的是 DeepSeek 的 token 和七牛云的存储/CDN 流量，跟服务器配置无关。

## 用户数据放哪

- **文字数据（账号、饮食记录、忌口爱好、分类缓存）→ 服务器的 SQLite 文件**，路径由 `SHIJI_DB_PATH` 指定，建议放 `server/data/shiji.db`。
- **照片 → 七牛云**（`QINIU_BUCKET` + `QINIU_DOMAIN=https://eating.xiaodaidai.site`）。
- 什么时候换数据库：单表百万级、或需要多台后端同时跑时，再把 `server/app/db.py` 换成 PostgreSQL/MySQL（只有这一个文件碰 SQL，改动可控）。

## 部署步骤

### 0. 前置
- 域名 `api.xiaodaidai.site` 解析到这台服务器（和网站同一个 IP 也行）。
- 服务器在国内的话，域名要已完成 ICP 备案（你既然在跑网站，应该已经有了）；七牛云用 `eating.xiaodaidai.site` 做自定义域名同样要求备案。
- 开放 80 / 443；`8010` **不要**对公网开放，只给 Nginx 本机访问。

### 1. 放代码
```bash
mkdir -p /www/wwwroot/shiji-api
cd /www/wwwroot/shiji-api
# 用 git（推荐）或者 rsync/scp 把仓库放进来，最终结构：
#   /www/wwwroot/shiji-api/server/{app,requirements.txt,data}
```

### 2. 首次把数据库带过去
本地开发库 `server/data/shiji.db` 里已经导好了 1211 条热量索引，直接拷过去最省事：
```bash
scp server/data/shiji.db root@服务器IP:/www/wwwroot/shiji-api/server/data/shiji.db
```
（不拷也行，服务端首次启动会自动建表，索引空着也不影响分类和记录。）

### 3. 配置环境变量
```bash
cp deploy/.env.example server/.env
vim server/.env      # 至少改 SHIJI_JWT_SECRET、DEEPSEEK_API_KEY、七牛/百度密钥
chmod 600 server/.env
```

### 4. 装依赖 + 起服务
```bash
cd /www/wwwroot/shiji-api/server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp ../deploy/shiji-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now shiji-api
systemctl status shiji-api
curl -s http://127.0.0.1:8010/health     # 应返回 {"status":"ok",...}
```

### 5. Nginx + HTTPS
```bash
cp deploy/nginx-api.conf /etc/nginx/conf.d/
# 没有证书就先注释掉 443 段里的 ssl_certificate 两行，然后：
certbot --nginx -d api.xiaodaidai.site
nginx -t && systemctl reload nginx
```
（用宝塔面板的话：新建一个「反向代理」站点，目标填 `http://127.0.0.1:8010`，再申请 Let's Encrypt 证书。）

### 6. 每日备份
```bash
chmod +x deploy/*.sh
crontab -e
# 加一行：
10 4 * * * /www/wwwroot/shiji-api/deploy/backup.sh >> /www/wwwlogs/shiji-backup.log 2>&1
```

### 7. 让 App 指向新地址
```bash
cd android
./gradlew assembleDebug -PapiBaseUrl=https://api.xiaodaidai.site/
```
以后打正式包同理（release 包只允许 HTTPS，正好匹配）。

## 上线前的检查清单

- [ ] `SHIJI_JWT_SECRET` 换成了随机串（默认值能被伪造登录态）
- [ ] **短信别再挂开发模式**：现在 `SHIJI_SMS_DEV_MODE=1` 时接口会把验证码直接回传，公网开放等于任何人都能登录任意手机号。要么先只在内网用，要么先把短信服务商接上（`server/app/services.py` 里的 `send_sms_code`），再把开关设成 0
- [ ] 全站 HTTPS（App 的 release 包也只允许 HTTPS）
- [ ] `8010` 端口没暴露到公网（`ss -lntp` 确认监听在 127.0.0.1）
- [ ] `.env` 权限 600，DeepSeek / 七牛 / 百度的密钥只在服务器上，别写进 App
- [ ] 备份任务跑过至少一次，能恢复（`sqlite3 备份文件 "select count(*) from meals;"`）
- [ ] AI 日配额设了（`SHIJI_AI_DAILY_PER_USER` / `SHIJI_AI_DAILY_TOTAL`），防止被人刷额度
- [ ] 服务器防火墙只放行 22 / 80 / 443

## 常看的几个命令

```bash
systemctl status shiji-api          # 服务状态
journalctl -u shiji-api -n 100      # 最近的日志
tail -f /www/wwwlogs/shiji-api.log  # 如果用的是 service 文件里的日志路径
curl -s https://api.xiaodaidai.site/health   # 外网健康检查
```

## 常见问题
## 方案 B：服务器上已经有 Docker

仓库根目录的 `docker-compose.yml` 已经按“宿主机已有网站”改好了：只把 API 绑到
`127.0.0.1:8010`，不抢 80/443，TLS 和域名仍然交给宿主机上现有的 Nginx。

```bash
cd /www/wwwroot/shiji-api
cp deploy/.env.example server/.env && vim server/.env
docker compose up -d --build
curl -s http://127.0.0.1:8010/health
```

数据存在 docker volume `shiji-data` 里；备份时先把它拷出来：
`docker compose exec api cp /data/shiji.db /data/backup-$(date +%F).db`。
容器里固定 1 个 worker（对话会话在进程内存里，多 worker 会串）。

## 常见问题

**Q：网站已经在跑 Nginx，会不会冲突？**
只要不是同一个 `server_name`、不抢 80/443 的默认站点就没问题；我们是给 `api.xiaodaidai.site` 单独加一个 server 块。

**Q：能不能和网站共用一个端口？**
不建议。后端固定用 8010，Nginx 按域名分流，最省心。

**Q：以后用户多了要扩容吗？**
先加内存/换数据库就够。真要横向扩，需要先把两处状态从进程里挪出去：对话会话（现在在内存，见 `CHAT_SESSIONS`）和 AI 配额计数。
