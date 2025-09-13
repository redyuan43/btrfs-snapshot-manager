#!/usr/bin/env python3
"""
API接口测试脚本
"""

import requests
import json
import time
import sys
from pathlib import Path

class APITester:
    def __init__(self, base_url="http://127.0.0.1:5000"):
        self.base_url = base_url

    def test_health(self):
        """测试健康检查"""
        print("🔍 测试健康检查...")
        try:
            response = requests.get(f"{self.base_url}/api/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 健康检查成功: {data['status']}")
                return True
            else:
                print(f"❌ 健康检查失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 健康检查异常: {e}")
            return False

    def test_config(self):
        """测试配置获取"""
        print("🔍 测试配置获取...")
        try:
            response = requests.get(f"{self.base_url}/api/config")
            if response.status_code == 200:
                config = response.json()
                print(f"✅ 配置获取成功")
                print(f"   监控目录: {config['watch_dir']}")
                print(f"   快照目录: {config['snapshot_dir']}")
                print(f"   最大快照数: {config['max_snapshots']}")
                return True
            else:
                print(f"❌ 配置获取失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 配置获取异常: {e}")
            return False

    def test_create_snapshot(self):
        """测试创建快照"""
        print("🔍 测试创建快照...")
        try:
            data = {"description": "API测试快照"}
            response = requests.post(f"{self.base_url}/api/snapshots", json=data)
            if response.status_code == 200:
                result = response.json()
                if result['success']:
                    print(f"✅ 快照创建成功: {result['snapshot']['name']}")
                    return True
                else:
                    print(f"❌ 快照创建失败: {result['message']}")
                    return False
            else:
                print(f"❌ 快照创建请求失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 快照创建异常: {e}")
            return False

    def test_list_snapshots(self):
        """测试列出快照"""
        print("🔍 测试列出快照...")
        try:
            response = requests.get(f"{self.base_url}/api/snapshots")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 快照列表获取成功，共 {data['count']} 个快照")
                for snapshot in data['snapshots'][:3]:  # 只显示前3个
                    print(f"   - {snapshot['name']} ({snapshot['created_time']})")
                return True
            else:
                print(f"❌ 快照列表获取失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 快照列表获取异常: {e}")
            return False

    def test_snapshot_info(self):
        """测试快照信息"""
        print("🔍 测试快照信息...")
        try:
            response = requests.get(f"{self.base_url}/api/snapshots/info")
            if response.status_code == 200:
                info = response.json()
                print(f"✅ 快照信息获取成功")
                print(f"   快照数量: {info['count']}")
                print(f"   总大小: {info.get('total_size', 'N/A')}")
                return True
            else:
                print(f"❌ 快照信息获取失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 快照信息获取异常: {e}")
            return False

    def test_cleanup(self):
        """测试快照清理"""
        print("🔍 测试快照清理...")
        try:
            response = requests.post(f"{self.base_url}/api/snapshots/cleanup")
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 快照清理成功，删除了 {result['count']} 个快照")
                return True
            else:
                print(f"❌ 快照清理失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 快照清理异常: {e}")
            return False

    def test_monitoring_status(self):
        """测试监控状态"""
        print("🔍 测试监控状态...")
        try:
            response = requests.get(f"{self.base_url}/api/monitoring")
            if response.status_code == 200:
                status = response.json()
                print(f"✅ 监控状态获取成功")
                print(f"   监控激活: {status['active']}")
                print(f"   监控目录: {status['watch_dir']}")
                return True
            else:
                print(f"❌ 监控状态获取失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 监控状态获取异常: {e}")
            return False

    def test_files_list(self):
        """测试文件列表"""
        print("🔍 测试文件列表...")
        try:
            response = requests.get(f"{self.base_url}/api/files")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 文件列表获取成功，共 {data['count']} 个文件")
                for file_info in data['files'][:3]:  # 只显示前3个
                    print(f"   - {file_info['name']} ({file_info['size']} bytes)")
                return True
            else:
                print(f"❌ 文件列表获取失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 文件列表获取异常: {e}")
            return False

    def test_stats(self):
        """测试系统统计"""
        print("🔍 测试系统统计...")
        try:
            response = requests.get(f"{self.base_url}/api/stats")
            if response.status_code == 200:
                stats = response.json()
                print(f"✅ 系统统计获取成功")
                print(f"   磁盘使用率: {stats['disk']['percent']:.1f}%")
                print(f"   CPU使用率: {stats['system']['cpu_percent']:.1f}%")
                print(f"   内存使用率: {stats['system']['memory_percent']:.1f}%")
                return True
            else:
                print(f"❌ 系统统计获取失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 系统统计获取异常: {e}")
            return False

    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("🚀 开始API接口测试")
        print("=" * 60)

        tests = [
            self.test_health,
            self.test_config,
            self.test_create_snapshot,
            self.test_list_snapshots,
            self.test_snapshot_info,
            self.test_cleanup,
            self.test_monitoring_status,
            self.test_files_list,
            self.test_stats
        ]

        results = []
        for test in tests:
            try:
                result = test()
                results.append(result)
                time.sleep(0.5)  # 避免请求过快
            except Exception as e:
                print(f"❌ 测试异常: {e}")
                results.append(False)

        # 统计结果
        passed = sum(results)
        total = len(results)

        print("\n" + "=" * 60)
        print("📊 测试结果")
        print("=" * 60)
        print(f"总测试数: {total}")
        print(f"通过: {passed} ✅")
        print(f"失败: {total - passed} ❌")
        print(f"成功率: {(passed/total*100):.1f}%")

        return passed == total


def main():
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://127.0.0.1:5000"

    print(f"测试API服务器: {base_url}")

    tester = APITester(base_url)
    success = tester.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()