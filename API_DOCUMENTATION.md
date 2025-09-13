# Btrfs Snapshot Manager API Documentation

## 概述

Btrfs快照管理器提供RESTful API接口，方便前端界面与后端服务进行交互。API服务器基于Flask构建，支持跨域请求。

**基础URL**: `http://127.0.0.1:5000`

## 启动API服务器

```bash
# 基本启动
source venv/bin/activate
python api_server.py

# 指定配置文件
python api_server.py -c config.yaml

# 指定host和端口
python api_server.py --host 0.0.0.0 --port 8080

# 开启调试模式
python api_server.py --debug
```

## API端点

### 1. 健康检查

**GET** `/api/health`

检查API服务器状态。

**响应示例**:
```json
{
  "status": "healthy",
  "timestamp": "2025-09-13T13:30:00.123456",
  "version": "1.0.0"
}
```

### 2. 配置管理

#### 获取配置
**GET** `/api/config`

获取当前系统配置。

**响应示例**:
```json
{
  "watch_dir": "/mnt/btrfs-test/test_data",
  "snapshot_dir": "/mnt/btrfs-test/snapshots",
  "max_snapshots": 50,
  "cleanup_mode": "count",
  "retention_days": 7,
  "cooldown_seconds": 60,
  "test_mode": false
}
```

### 3. 快照管理

#### 列出所有快照
**GET** `/api/snapshots`

获取所有快照列表。

**响应示例**:
```json
{
  "snapshots": [
    {
      "name": "test_data_20250913_133000_123",
      "path": "/mnt/btrfs-test/snapshots/test_data_20250913_133000_123",
      "created_time": "2025-09-13T13:30:00.123456",
      "size": 1024000
    }
  ],
  "count": 1
}
```

#### 创建快照
**POST** `/api/snapshots`

手动创建新快照。

**请求体**:
```json
{
  "description": "手动创建的快照"
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "Snapshot created successfully",
  "snapshot": {
    "name": "test_data_20250913_133500_456",
    "path": "/mnt/btrfs-test/snapshots/test_data_20250913_133500_456",
    "created_time": "2025-09-13T13:35:00.456789"
  }
}
```

#### 删除快照
**DELETE** `/api/snapshots/<snapshot_name>`

删除指定名称的快照。

**响应示例**:
```json
{
  "success": true,
  "message": "Snapshot test_data_20250913_133000_123 deleted successfully"
}
```

#### 清理旧快照
**POST** `/api/snapshots/cleanup`

根据配置的清理策略清理旧快照。

**响应示例**:
```json
{
  "success": true,
  "message": "Cleaned up 3 old snapshots",
  "deleted_snapshots": [
    "/mnt/btrfs-test/snapshots/test_data_20250913_120000_001",
    "/mnt/btrfs-test/snapshots/test_data_20250913_121000_002",
    "/mnt/btrfs-test/snapshots/test_data_20250913_122000_003"
  ],
  "count": 3
}
```

#### 获取快照信息
**GET** `/api/snapshots/info`

获取快照统计信息。

**响应示例**:
```json
{
  "count": 15,
  "total_size": 1073741824,
  "oldest": "test_data_20250913_100000_001",
  "newest": "test_data_20250913_133500_456",
  "last_snapshot_time": "2025-09-13T13:35:00.456789"
}
```

### 4. 文件监控管理

#### 获取监控状态
**GET** `/api/monitoring`

获取当前文件监控状态。

**响应示例**:
```json
{
  "active": true,
  "watch_dir": "/mnt/btrfs-test/test_data",
  "watcher_alive": true
}
```

#### 启动文件监控
**POST** `/api/monitoring/start`

启动自动文件监控。

**响应示例**:
```json
{
  "success": true,
  "message": "File monitoring started"
}
```

#### 停止文件监控
**POST** `/api/monitoring/stop`

停止自动文件监控。

**响应示例**:
```json
{
  "success": true,
  "message": "File monitoring stopped"
}
```

### 5. 文件管理

#### 列出监控目录文件
**GET** `/api/files`

获取监控目录中的所有文件。

**响应示例**:
```json
{
  "files": [
    {
      "name": "document1.txt",
      "path": "document1.txt",
      "full_path": "/mnt/btrfs-test/test_data/document1.txt",
      "size": 1024,
      "modified_time": "2025-09-13T13:30:00.123456"
    },
    {
      "name": "nested.txt",
      "path": "subdir/nested.txt",
      "full_path": "/mnt/btrfs-test/test_data/subdir/nested.txt",
      "size": 512,
      "modified_time": "2025-09-13T13:25:00.789012"
    }
  ],
  "count": 2,
  "watch_dir": "/mnt/btrfs-test/test_data"
}
```

### 6. 系统统计

#### 获取系统统计信息
**GET** `/api/stats`

获取系统资源使用情况和快照统计。

**响应示例**:
```json
{
  "disk": {
    "total": 2097152000,
    "used": 104857600,
    "free": 1992294400,
    "percent": 5.0
  },
  "system": {
    "cpu_percent": 12.5,
    "memory_percent": 45.2,
    "load_avg": [0.5, 0.6, 0.7]
  },
  "snapshots": {
    "count": 15,
    "total_size": 1073741824,
    "oldest": "test_data_20250913_100000_001",
    "newest": "test_data_20250913_133500_456"
  },
  "monitoring": {
    "active": true,
    "uptime": 3600.5
  }
}
```

## 错误处理

### HTTP状态码

- `200 OK`: 请求成功
- `400 Bad Request`: 请求参数错误或操作失败
- `404 Not Found`: 资源不存在
- `500 Internal Server Error`: 服务器内部错误

### 错误响应格式

```json
{
  "error": "错误描述信息"
}
```

### 操作失败响应格式

```json
{
  "success": false,
  "message": "操作失败的具体原因"
}
```

## 前端集成示例

### JavaScript/Fetch API

```javascript
// 获取快照列表
async function getSnapshots() {
  try {
    const response = await fetch('/api/snapshots');
    const data = await response.json();
    console.log('快照列表:', data.snapshots);
    return data.snapshots;
  } catch (error) {
    console.error('获取快照列表失败:', error);
  }
}

// 创建快照
async function createSnapshot(description = '手动快照') {
  try {
    const response = await fetch('/api/snapshots', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ description })
    });
    const data = await response.json();
    if (data.success) {
      console.log('快照创建成功:', data.snapshot);
      return data.snapshot;
    } else {
      console.error('快照创建失败:', data.message);
    }
  } catch (error) {
    console.error('创建快照时发生错误:', error);
  }
}

// 启动监控
async function startMonitoring() {
  try {
    const response = await fetch('/api/monitoring/start', {
      method: 'POST'
    });
    const data = await response.json();
    if (data.success) {
      console.log('监控已启动');
    } else {
      console.error('启动监控失败:', data.message);
    }
  } catch (error) {
    console.error('启动监控时发生错误:', error);
  }
}

// 获取系统统计
async function getStats() {
  try {
    const response = await fetch('/api/stats');
    const stats = await response.json();
    console.log('系统统计:', stats);
    return stats;
  } catch (error) {
    console.error('获取系统统计失败:', error);
  }
}
```

### React 示例

```jsx
import React, { useState, useEffect } from 'react';

function SnapshotManager() {
  const [snapshots, setSnapshots] = useState([]);
  const [monitoring, setMonitoring] = useState(false);
  const [stats, setStats] = useState(null);

  // 获取快照列表
  const fetchSnapshots = async () => {
    try {
      const response = await fetch('/api/snapshots');
      const data = await response.json();
      setSnapshots(data.snapshots);
    } catch (error) {
      console.error('Failed to fetch snapshots:', error);
    }
  };

  // 创建快照
  const createSnapshot = async () => {
    try {
      const response = await fetch('/api/snapshots', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: 'React界面创建' })
      });
      const data = await response.json();
      if (data.success) {
        fetchSnapshots(); // 刷新列表
      }
    } catch (error) {
      console.error('Failed to create snapshot:', error);
    }
  };

  // 切换监控状态
  const toggleMonitoring = async () => {
    try {
      const endpoint = monitoring ? '/api/monitoring/stop' : '/api/monitoring/start';
      const response = await fetch(endpoint, { method: 'POST' });
      const data = await response.json();
      if (data.success) {
        setMonitoring(!monitoring);
      }
    } catch (error) {
      console.error('Failed to toggle monitoring:', error);
    }
  };

  useEffect(() => {
    fetchSnapshots();
    // 定期刷新数据
    const interval = setInterval(() => {
      fetchSnapshots();
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <h1>Btrfs快照管理器</h1>

      <div>
        <button onClick={createSnapshot}>创建快照</button>
        <button onClick={toggleMonitoring}>
          {monitoring ? '停止监控' : '启动监控'}
        </button>
      </div>

      <div>
        <h2>快照列表 ({snapshots.length})</h2>
        <ul>
          {snapshots.map(snapshot => (
            <li key={snapshot.name}>
              {snapshot.name} - {snapshot.created_time}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default SnapshotManager;
```

## 测试

运行API测试脚本：

```bash
# 启动API服务器（在一个终端）
source venv/bin/activate
python api_server.py --debug

# 运行测试（在另一个终端）
source venv/bin/activate
python tests/test_api.py
```

## 安全注意事项

1. **CORS配置**: 生产环境中应限制允许的域名
2. **认证授权**: 生产环境建议添加API密钥或JWT认证
3. **输入验证**: API已包含基本的错误处理，但建议根据需要增强
4. **HTTPS**: 生产环境应使用HTTPS
5. **速率限制**: 考虑添加API调用频率限制

## 部署建议

```bash
# 使用Gunicorn部署（生产环境）
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 api_server:app

# 使用systemd管理API服务
sudo systemctl enable btrfs-api
sudo systemctl start btrfs-api
```