#!/usr/bin/env bash
# 从本机 Chrome（你已登录 x.com 的那个 profile）解密 auth_token，直接写入 RSSHub 的 .env。
# 设计成你自己跑——token 不经过 agent。会弹一次钥匙串授权框（读 "Chrome Safe Storage"），点允许。
#
# 用法： bash grab_x_cookie.sh            # 默认 Default profile
#        bash grab_x_cookie.sh "Profile 1"
set -euo pipefail

PROFILE="${1:-Default}"
CHROME_DIR="$HOME/Library/Application Support/Google/Chrome/$PROFILE"
DATA="${ASTA_NEWS_HOME:-$HOME/.claude/plugins/data/asta-news}"
ENV_FILE="$DATA/rsshub/.env"

[ -f "$CHROME_DIR/Cookies" ] || { echo "找不到 $CHROME_DIR/Cookies"; exit 1; }

KEY=$(security find-generic-password -wa "Chrome Safe Storage") || { echo "未授权读取钥匙串，已取消"; exit 1; }

cp "$CHROME_DIR/Cookies" /tmp/_ck.db
TOKEN=$(uv run --quiet --with pycryptodome python3 - "$KEY" <<'PY'
import sys, sqlite3, hashlib, re
from Crypto.Cipher import AES
key = hashlib.pbkdf2_hmac('sha1', sys.argv[1].encode(), b'saltysalt', 1003, dklen=16)
db = sqlite3.connect('/tmp/_ck.db')
row = db.execute("SELECT encrypted_value FROM cookies WHERE host_key LIKE '%x.com%' AND name='auth_token'").fetchone()
if not row: sys.exit("该 profile 里没有 x.com 的 auth_token，确认登录的是这个 profile")
enc = row[0]
enc = enc[3:] if enc[:3] in (b'v10', b'v11') else enc
dec = AES.new(key, AES.MODE_CBC, b' '*16).decrypt(enc)
dec = dec[:-dec[-1]].decode('utf-8', 'ignore')
m = re.search(r'[0-9a-f]{40}', dec)
print(m.group(0) if m else dec[-40:])
PY
)
rm -f /tmp/_ck.db

[ -n "$TOKEN" ] || { echo "解密失败"; exit 1; }
mkdir -p "$(dirname "$ENV_FILE")"; touch "$ENV_FILE"
# 替换或追加 TWITTER_AUTH_TOKEN 行
if grep -q '^TWITTER_AUTH_TOKEN=' "$ENV_FILE"; then
  sed -i '' "s|^TWITTER_AUTH_TOKEN=.*|TWITTER_AUTH_TOKEN=$TOKEN|" "$ENV_FILE"
else
  echo "TWITTER_AUTH_TOKEN=$TOKEN" >> "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"
echo "✓ auth_token 已写入 $ENV_FILE（长度 ${#TOKEN}）"
echo "  重启容器生效： cd $DATA/rsshub && docker compose up -d"
