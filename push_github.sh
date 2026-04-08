#!/bin/bash
# push_github.sh - 一键推送到 GitHub
# 用法: ./push_github.sh "commit message"  或  ./push_github.sh (自动生成提交信息)

cd "$(dirname "$0")"

COMMIT_MSG="${1:-update $(date '+%Y-%m-%d %H:%M')}"

git add -A
git commit -m "$COMMIT_MSG" --allow-empty
git push origin main
