#!/bin/bash

# 快速更新服务器脚本
# 用法: bash update_server.sh [服务器IP]

SERVER_IP="${1:-192.168.100.97}"
SERVER_USER="${2:-root}"

echo "🚀 开始更新服务器 $SERVER_IP ..."

# 1. 本地提交代码
echo "📝 提交本地更改..."
git add .
read -p "请输入提交信息: " commit_msg
git commit -m "$commit_msg"
git push

echo "✅ 代码已推送到GitHub"

# 2. 在服务器上更新
echo "🔄 更新服务器..."
ssh $SERVER_USER@$SERVER_IP << 'EOF'
cd /opt/btrfs-snapshot-manager
echo "拉取最新代码..."
git pull origin master
echo "重新构建服务..."
docker-compose build
echo "重启服务..."
docker-compose up -d
echo "检查服务状态..."
docker-compose ps
EOF

echo "🎉 服务器更新完成！"
echo "📱 访问地址: http://$SERVER_IP"