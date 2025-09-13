#!/bin/bash

echo "=== 修复Btrfs子卷设置 ==="

# 检查btrfs挂载
if ! mount | grep -q "/mnt/btrfs-test"; then
    echo "❌ Btrfs文件系统未挂载到 /mnt/btrfs-test"
    exit 1
fi

echo "📁 当前 /mnt/btrfs-test 内容："
ls -la /mnt/btrfs-test/

echo ""
echo "🔍 检查现有的子卷..."
echo "现有子卷列表："
btrfs subvolume list /mnt/btrfs-test 2>/dev/null || echo "  (无子卷)"

echo ""
echo "⚠️  问题诊断："
echo "当前的 test_data 是普通目录，不是Btrfs子卷"
echo "只有Btrfs子卷才能创建快照"

echo ""
echo "🛠️  修复方案："
echo "1. 备份现有的 test_data 目录"
echo "2. 删除原目录"
echo "3. 创建新的Btrfs子卷"
echo "4. 恢复数据"

read -p "是否继续修复？(y/N): " -r
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "操作取消"
    exit 0
fi

# 备份现有数据
echo ""
echo "📦 备份现有数据..."
if [ -d "/mnt/btrfs-test/test_data" ]; then
    cp -r /mnt/btrfs-test/test_data /tmp/test_data_backup
    echo "✅ 数据已备份到 /tmp/test_data_backup"
fi

# 删除原目录
echo ""
echo "🗑️  删除原目录..."
rm -rf /mnt/btrfs-test/test_data

# 创建Btrfs子卷
echo ""
echo "🔧 创建Btrfs子卷..."
if btrfs subvolume create /mnt/btrfs-test/test_data; then
    echo "✅ Btrfs子卷 'test_data' 创建成功"
else
    echo "❌ 子卷创建失败"
    exit 1
fi

# 恢复数据
echo ""
echo "📤 恢复数据..."
if [ -d "/tmp/test_data_backup" ]; then
    cp -r /tmp/test_data_backup/* /mnt/btrfs-test/test_data/ 2>/dev/null || echo "  (无数据需要恢复)"
    rm -rf /tmp/test_data_backup
    echo "✅ 数据已恢复"
fi

# 添加一些测试文件
echo ""
echo "📝 添加测试文件..."
echo "Hello Btrfs Subvolume $(date)" > /mnt/btrfs-test/test_data/hello.txt
echo "Test document content" > /mnt/btrfs-test/test_data/document.txt
mkdir -p /mnt/btrfs-test/test_data/subdir
echo "Nested file content" > /mnt/btrfs-test/test_data/subdir/nested.txt

# 设置权限
chown -R $USER:$USER /mnt/btrfs-test/test_data

# 验证设置
echo ""
echo "✅ 验证设置..."
echo "子卷列表："
btrfs subvolume list /mnt/btrfs-test

echo ""
echo "测试数据目录内容："
ls -la /mnt/btrfs-test/test_data/

echo ""
echo "🎉 Btrfs子卷设置完成！"
echo ""
echo "现在可以测试快照功能："
echo "sudo btrfs subvolume snapshot /mnt/btrfs-test/test_data /mnt/btrfs-test/snapshots/manual_test"