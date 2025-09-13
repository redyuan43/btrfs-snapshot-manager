#!/bin/bash

# 需要在sudo权限下执行此脚本
# Usage: sudo bash test_real_btrfs.sh

set -e

echo "========================================"
echo "🚀 Btrfs快照管理器 - 真实环境测试"
echo "========================================"

# 检查是否以root身份运行
if [[ $EUID -ne 0 ]]; then
   echo "❌ 此脚本需要root权限运行"
   echo "请使用: sudo bash test_real_btrfs.sh"
   exit 1
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "❌ 虚拟环境不存在，请先运行: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source venv/bin/activate

# 检查Btrfs挂载
echo "🔍 检查Btrfs环境..."
if ! mount | grep -q "/mnt/btrfs-test"; then
    echo "❌ Btrfs文件系统未挂载"
    exit 1
fi

if [ ! -d "/mnt/btrfs-test/test_data" ]; then
    echo "❌ test_data子卷不存在"
    exit 1
fi

echo "✅ Btrfs环境正常"

# 显示初始状态
echo ""
echo "📊 初始状态："
echo "监控目录: /mnt/btrfs-test/test_data"
echo "快照目录: /mnt/btrfs-test/snapshots"
echo ""
echo "test_data内容："
ls -la /mnt/btrfs-test/test_data/
echo ""
echo "现有快照："
ls -la /mnt/btrfs-test/snapshots/ 2>/dev/null || echo "  (无快照)"

# 测试1: 手动创建快照
echo ""
echo "🧪 测试1: 手动创建快照"
echo "================================"
python btrfs_snapshot_manager.py -c real_btrfs_test_config.yaml --snapshot-now

if [ $? -eq 0 ]; then
    echo "✅ 手动快照创建成功"
else
    echo "❌ 手动快照创建失败"
fi

# 显示快照
echo ""
echo "📋 当前快照列表："
python btrfs_snapshot_manager.py -c real_btrfs_test_config.yaml --list

# 测试2: 创建更多快照
echo ""
echo "🧪 测试2: 创建多个快照"
echo "================================"
for i in {1..3}; do
    echo "创建第${i}个测试快照..."

    # 修改测试文件触发变化
    echo "Test content ${i} - $(date)" >> /mnt/btrfs-test/test_data/test_${i}.txt

    # 创建快照
    python btrfs_snapshot_manager.py -c real_btrfs_test_config.yaml --snapshot-now

    if [ $? -eq 0 ]; then
        echo "✅ 快照 ${i} 创建成功"
    else
        echo "❌ 快照 ${i} 创建失败"
    fi

    sleep 1
done

# 显示所有快照
echo ""
echo "📋 所有快照："
python btrfs_snapshot_manager.py -c real_btrfs_test_config.yaml --list

# 测试3: 使用btrfs命令验证快照
echo ""
echo "🧪 测试3: 验证快照内容"
echo "================================"
echo "使用btrfs命令列出子卷："
btrfs subvolume list /mnt/btrfs-test 2>/dev/null || echo "需要更高权限或btrfs命令不可用"

echo ""
echo "快照目录结构："
find /mnt/btrfs-test/snapshots -type d -name "test_data_*" 2>/dev/null | head -3 | while read snapshot; do
    if [ -d "$snapshot" ]; then
        echo "快照: $(basename $snapshot)"
        echo "  文件数: $(find $snapshot -type f | wc -l)"
        echo "  大小: $(du -sh $snapshot | cut -f1)"
    fi
done

# 测试4: 快照内容验证
echo ""
echo "🧪 测试4: 快照内容完整性验证"
echo "================================"
latest_snapshot=$(find /mnt/btrfs-test/snapshots -type d -name "test_data_*" | sort | tail -1)
if [ -n "$latest_snapshot" ] && [ -d "$latest_snapshot" ]; then
    echo "最新快照: $(basename $latest_snapshot)"
    echo "快照内容："
    ls -la "$latest_snapshot" | head -10

    # 验证文件内容
    if [ -f "$latest_snapshot/hello.txt" ]; then
        echo ""
        echo "快照中的hello.txt内容:"
        cat "$latest_snapshot/hello.txt"
    fi
else
    echo "❌ 未找到快照"
fi

# 测试5: 清理功能
echo ""
echo "🧪 测试5: 快照清理功能"
echo "================================"
echo "清理前快照数量: $(find /mnt/btrfs-test/snapshots -type d -name "test_data_*" | wc -l)"

python btrfs_snapshot_manager.py -c real_btrfs_test_config.yaml --cleanup

if [ $? -eq 0 ]; then
    echo "✅ 快照清理完成"
    echo "清理后快照数量: $(find /mnt/btrfs-test/snapshots -type d -name "test_data_*" | wc -l)"
else
    echo "❌ 快照清理失败"
fi

# 测试6: API服务器测试
echo ""
echo "🧪 测试6: API服务器快速测试"
echo "================================"
echo "启动API服务器进行快照创建测试..."

# 在后台启动API服务器
timeout 10s python api_server.py -c real_btrfs_test_config.yaml --host 127.0.0.1 --port 5555 > /tmp/api_test.log 2>&1 &
API_PID=$!

# 等待API服务器启动
sleep 3

# 测试API快照创建
echo "通过API创建快照..."
curl -s -X POST http://127.0.0.1:5555/api/snapshots \
    -H "Content-Type: application/json" \
    -d '{"description": "API测试快照"}' > /tmp/api_response.json

if [ $? -eq 0 ]; then
    echo "✅ API快照创建请求发送成功"
    echo "API响应:"
    cat /tmp/api_response.json
    echo ""
else
    echo "❌ API快照创建失败"
fi

# 停止API服务器
kill $API_PID 2>/dev/null || true

# 最终报告
echo ""
echo "========================================"
echo "📊 测试完成报告"
echo "========================================"

final_snapshots=$(find /mnt/btrfs-test/snapshots -type d -name "test_data_*" | wc -l)
echo "总快照数量: $final_snapshots"
echo "测试数据目录: /mnt/btrfs-test/test_data"
echo "快照存储目录: /mnt/btrfs-test/snapshots"

echo ""
echo "快照详情:"
find /mnt/btrfs-test/snapshots -type d -name "test_data_*" | sort | while read snapshot; do
    if [ -d "$snapshot" ]; then
        size=$(du -sh "$snapshot" 2>/dev/null | cut -f1)
        files=$(find "$snapshot" -type f 2>/dev/null | wc -l)
        echo "  - $(basename $snapshot): ${files}个文件, ${size}"
    fi
done

echo ""
echo "🎉 真实Btrfs环境测试完成！"
echo ""
echo "接下来可以："
echo "1. 运行文件监控: python btrfs_snapshot_manager.py -c real_btrfs_test_config.yaml"
echo "2. 启动API服务: python api_server.py -c real_btrfs_test_config.yaml"
echo "3. 查看日志: tail -f /tmp/real_btrfs_test.log"

# 清理临时文件
rm -f /tmp/api_response.json /tmp/api_test.log

deactivate