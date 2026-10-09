#!/usr/bin/env bash
# 部署 / 更新脚本：在服务器上执行
#   APP_DIR=/www/wwwroot/shiji-api bash deploy.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/www/wwwroot/shiji-api}"
APP_USER="${APP_USER:-www}"

cd "$APP_DIR"

echo "==> 拉取最新代码"
if [ -d .git ]; then
  git pull --ff-only
else
  echo "    （不是 git 目录，跳过；请自行 rsync/scp 上传）"
fi

SERVER_DIR="$APP_DIR/server"
cd "$SERVER_DIR"

echo "==> 准备虚拟环境"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -U pip -q
.venv/bin/pip install -r requirements.txt -q

echo "==> 检查配置"
if [ ! -f .env ]; then
  echo "    缺少 $SERVER_DIR/.env，先从 deploy/.env.example 复制一份并填写"
  exit 1
fi
if grep -q "please-change-me" .env; then
  echo "    ⚠️  .env 里的 SHIJI_JWT_SECRET 还是默认值，上线前必须改"
fi
if grep -q "SHIJI_SMS_DEV_MODE=1" .env; then
  echo "    ⚠️  短信还是开发模式（接口会直接返回验证码），公网开放前必须接真实短信服务商"
fi

mkdir -p "$APP_DIR/server/data"
chown -R "$APP_USER:$APP_USER" "$APP_DIR/server/data" 2>/dev/null || true

echo "==> 重启服务"
systemctl restart shiji-api
sleep 2
systemctl --no-pager --lines=5 status shiji-api || true

echo "==> 健康检查"
curl -fsS http://127.0.0.1:8010/health && echo
