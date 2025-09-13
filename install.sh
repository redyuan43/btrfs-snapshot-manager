#!/bin/bash

set -e

# 配置路径
INSTALL_DIR="/opt/btrfs-snapshot-manager"
CONFIG_DIR="/etc/btrfs-snapshot-manager"
SERVICE_FILE="systemd/btrfs-snapshot-manager.service"
SYSTEMD_DIR="/etc/systemd/system"
VENV_DIR="$INSTALL_DIR/venv"
CURRENT_DIR="$(pwd)"

echo "==================================="
echo "Btrfs Snapshot Manager Installation"
echo "==================================="
echo ""

# 检查是否需要 root 权限（只在系统级安装时需要）
NEED_SUDO=false
if [ "$1" = "--user" ]; then
    echo "Installing in user mode (no systemd service)..."
    INSTALL_DIR="$HOME/.local/btrfs-snapshot-manager"
    CONFIG_DIR="$HOME/.config/btrfs-snapshot-manager"
    VENV_DIR="$INSTALL_DIR/venv"
else
    echo "Installing system-wide (requires sudo for systemd service)..."
    NEED_SUDO=true
    if [[ $EUID -ne 0 ]]; then
        echo "ERROR: System-wide installation requires root privileges"
        echo "Please run: sudo bash install.sh"
        echo "Or for user installation: bash install.sh --user"
        exit 1
    fi
fi

# 检查 Python 3
echo "Checking Python 3..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3 first: sudo apt install python3 python3-venv"
    exit 1
fi

# 检查 btrfs-progs
echo "Checking for btrfs-progs..."
if ! command -v btrfs &> /dev/null; then
    echo "WARNING: btrfs command not found"
    echo "For production use, please install: sudo apt install btrfs-progs"
    echo "Continuing installation (test mode will still work)..."
    echo ""
fi

# 创建安装目录
echo "Creating installation directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"

# 创建虚拟环境
echo "Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"

# 激活虚拟环境并安装依赖
echo "Installing Python dependencies in virtual environment..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$CURRENT_DIR/requirements.txt"
deactivate

# 复制程序文件
echo "Copying program files..."
cp -r "$CURRENT_DIR"/*.py "$INSTALL_DIR/"
cp "$CURRENT_DIR/requirements.txt" "$INSTALL_DIR/"

# 创建启动脚本（包装虚拟环境）
echo "Creating wrapper script..."
cat > "$INSTALL_DIR/btrfs-snapshot-manager" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate"
exec python "$SCRIPT_DIR/btrfs_snapshot_manager.py" "$@"
EOF
chmod +x "$INSTALL_DIR/btrfs-snapshot-manager"

# 安装配置文件
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    echo "Installing default configuration..."
    cp "$CURRENT_DIR/config.yaml" "$CONFIG_DIR/"
    echo "Configuration installed to: $CONFIG_DIR/config.yaml"
else
    echo "Configuration file already exists, skipping..."
fi

# 系统级安装：安装 systemd 服务
if [ "$NEED_SUDO" = true ]; then
    echo "Installing systemd service..."

    # 创建自定义的 service 文件，使用虚拟环境
    cat > "$SYSTEMD_DIR/btrfs-snapshot-manager.service" << EOF
[Unit]
Description=Btrfs Automatic Snapshot Manager
Documentation=https://github.com/yourusername/btrfs-snapshot-manager
After=multi-user.target
Wants=multi-user.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/btrfs-snapshot-manager -c $CONFIG_DIR/config.yaml
Restart=always
RestartSec=10
User=root
Group=root

# Security settings
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/data /var/log
NoNewPrivileges=yes

# Resource limits
CPUQuota=50%
MemoryLimit=512M
TasksMax=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=btrfs-snapshot-manager

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    echo "Systemd service installed"
fi

# 创建命令行快捷方式（用户模式）
if [ "$NEED_SUDO" = false ]; then
    echo "Creating user command shortcut..."
    mkdir -p "$HOME/.local/bin"
    ln -sf "$INSTALL_DIR/btrfs-snapshot-manager" "$HOME/.local/bin/btrfs-snapshot-manager"
    echo "Command installed to: ~/.local/bin/btrfs-snapshot-manager"
    echo "Make sure ~/.local/bin is in your PATH"
fi

echo ""
echo "========================================="
echo "Installation complete!"
echo "========================================="
echo ""

if [ "$NEED_SUDO" = true ]; then
    echo "System-wide installation completed."
    echo ""
    echo "Next steps:"
    echo "1. Edit configuration: sudo nano $CONFIG_DIR/config.yaml"
    echo "2. Enable service: sudo systemctl enable btrfs-snapshot-manager"
    echo "3. Start service: sudo systemctl start btrfs-snapshot-manager"
    echo "4. Check status: sudo systemctl status btrfs-snapshot-manager"
    echo "5. View logs: sudo journalctl -u btrfs-snapshot-manager -f"
else
    echo "User installation completed."
    echo ""
    echo "Next steps:"
    echo "1. Edit configuration: nano $CONFIG_DIR/config.yaml"
    echo "2. Run manually: $INSTALL_DIR/btrfs-snapshot-manager"
    echo "   Or if ~/.local/bin is in PATH: btrfs-snapshot-manager"
fi

echo ""
echo "Testing commands:"
echo "  # Test mode (no root required):"
echo "  $INSTALL_DIR/btrfs-snapshot-manager --test-mode \\"
echo "    --watch-dir /tmp/test_dir --snapshot-dir /tmp/snapshots"
echo ""
echo "  # List snapshots:"
echo "  $INSTALL_DIR/btrfs-snapshot-manager --list"
echo ""
echo "  # Create snapshot manually:"
echo "  $INSTALL_DIR/btrfs-snapshot-manager --snapshot-now"