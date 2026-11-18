#!/usr/bin/env bash
# 提交并推送到 Xmond1234/xauusd- 的 main。令牌只从环境变量 GITHUB_XAUUSD_TOKEN 读取，不写入 .git/config，不打印。
set -euo pipefail
set +x
cd "$(dirname "$0")"
REPO_URL="https://github.com/Xmond1234/xauusd-.git"
[ -n "${GITHUB_XAUUSD_TOKEN:-}" ] || { echo "push.sh: 缺少 GITHUB_XAUUSD_TOKEN" >&2; exit 2; }
if [ ! -d .git ]; then git init -q -b main; fi
git config user.name  >/dev/null || git config user.name "XAUUSD 总指挥 Bot"
git config user.email >/dev/null || git config user.email "bot@users.noreply.github.com"
git remote get-url origin >/dev/null 2>&1 || git remote add origin "$REPO_URL"
git add -A index.html data.json build_data.py push.sh UPDATE.md .gitignore .nojekyll 2>/dev/null || git add -A
if git diff --cached --quiet; then echo "push.sh: 没有变化"; else
  git commit -q -m "update $(TZ=Asia/Kuala_Lumpur date '+%Y-%m-%d %H:%M') UTC+8"; fi
AUTH="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$GITHUB_XAUUSD_TOKEN" | base64 -w0)"
if ! git -c http.extraheader="$AUTH" push -q origin HEAD:main >/tmp/xauusd-push.log 2>&1; then
  # 远端有别的提交时先合并再推
  if git -c http.extraheader="$AUTH" pull -q --rebase -X ours origin main >>/tmp/xauusd-push.log 2>&1 && \
     git -c http.extraheader="$AUTH" push -q origin HEAD:main >>/tmp/xauusd-push.log 2>&1; then :; else
    sed -i 's/x-access-token:[^@ ]*/x-access-token:***/g' /tmp/xauusd-push.log
    echo "push.sh: 推送失败（详情 /tmp/xauusd-push.log）" >&2; exit 1; fi
fi
echo "push.sh: 已推送 $(git rev-parse --short HEAD)"
