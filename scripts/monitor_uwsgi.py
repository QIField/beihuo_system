#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
uWSGI 进程监控脚本
用于监控 uWSGI worker 的健康状态，帮助诊断问题

使用方法:
    python scripts/monitor_uwsgi.py

功能:
    1. 显示当前 uWSGI 进程状态
    2. 监控 worker 重启次数
    3. 检测异常崩溃
    4. 提供重启建议
"""

import os
import sys
import time
import subprocess
import re
from datetime import datetime
from collections import defaultdict


class UWSGIMonitor:
    """uWSGI 进程监控器"""

    def __init__(self, log_path='/www/wwwlogs/python/beihuo_system/uwsgi.log'):
        self.log_path = log_path
        self.stats = {
            'worker_restarts': defaultdict(int),
            'segfaults': 0,
            'memory_kills': 0,
            'harakiri_kills': 0,
            'last_check': None
        }

    def check_processes(self):
        """检查当前 uWSGI 进程状态"""
        print("\n" + "=" * 60)
        print(f"uWSGI 进程状态检查 - {datetime.now()}")
        print("=" * 60)

        try:
            # 查找 uWSGI 进程
            result = subprocess.run(
                ['ps', 'aux'],
                capture_output=True,
                text=True
            )

            uwsgi_processes = []
            for line in result.stdout.split('\n'):
                if 'uwsgi' in line.lower() and 'python' in line.lower():
                    uwsgi_processes.append(line)

            if not uwsgi_processes:
                print("⚠️  未找到 uWSGI 进程")
                return False

            print(f"✅ 找到 {len(uwsgi_processes)} 个 uWSGI 相关进程:\n")

            master_pid = None
            worker_pids = []

            for proc in uwsgi_processes:
                parts = proc.split()
                if len(parts) >= 11:
                    pid = parts[1]
                    cpu = parts[2]
                    mem = parts[3]
                    cmd = ' '.join(parts[10:])

                    if 'master' in cmd.lower():
                        master_pid = pid
                        print(f"  👑 Master PID: {pid} (CPU: {cpu}%, MEM: {mem}%)")
                    else:
                        worker_pids.append(pid)
                        print(f"  👷 Worker PID: {pid} (CPU: {cpu}%, MEM: {mem}%)")

            print(f"\n📊 总结: 1 个 Master, {len(worker_pids)} 个 Workers")
            return True

        except Exception as e:
            print(f"❌ 检查进程时出错: {e}")
            return False

    def analyze_logs(self, lines=100):
        """分析最近的日志"""
        print("\n" + "=" * 60)
        print(f"日志分析 (最近 {lines} 行)")
        print("=" * 60)

        if not os.path.exists(self.log_path):
            print(f"⚠️  日志文件不存在: {self.log_path}")
            return

        try:
            # 读取日志文件
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()

            # 只分析最近的行
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

            # 统计各种事件
            segfault_count = 0
            worker_restarts = defaultdict(int)
            memory_issues = 0
            harakiri_count = 0

            for line in recent_lines:
                # 检测段错误
                if 'Segmentation Fault' in line or 'segfault' in line.lower():
                    segfault_count += 1

                # 检测 worker 重启
                match = re.search(r'worker (\d+).*restarted', line, re.IGNORECASE)
                if match:
                    worker_id = match.group(1)
                    worker_restarts[worker_id] += 1

                # 检测内存问题
                if 'memory' in line.lower() and ('kill' in line.lower() or 'limit' in line.lower()):
                    memory_issues += 1

                # 检测 harakiri（超时）
                if 'harakiri' in line.lower():
                    harakiri_count += 1

            # 输出统计结果
            print(f"\n📈 最近 {len(recent_lines)} 行日志统计:")
            print(f"   段错误 (Segmentation Fault): {segfault_count}")
            print(f"   Worker 重启次数:")
            for worker_id, count in sorted(worker_restarts.items()):
                print(f"     - Worker {worker_id}: {count} 次")
            print(f"   内存问题: {memory_issues}")
            print(f"   请求超时 (Harakiri): {harakiri_count}")

            # 健康评估
            print("\n🏥 健康评估:")
            if segfault_count > 0:
                print("   ❌ 严重: 检测到段错误，应用可能不稳定")
                print("   💡 建议: 检查代码中的 C 扩展或内存操作")
            elif sum(worker_restarts.values()) > 10:
                print("   ⚠️  警告: Worker 重启次数过多")
                print("   💡 建议: 检查内存泄漏或调整 max-requests 设置")
            elif harakiri_count > 5:
                print("   ⚠️  警告: 请求超时次数较多")
                print("   💡 建议: 优化慢查询或增加 harakiri 超时时间")
            else:
                print("   ✅ 健康: 未发现明显问题")

        except Exception as e:
            print(f"❌ 分析日志时出错: {e}")

    def tail_logs(self, follow=True, lines=20):
        """实时查看日志"""
        print("\n" + "=" * 60)
        print(f"实时日志监控 (按 Ctrl+C 退出)")
        print("=" * 60)

        if not os.path.exists(self.log_path):
            print(f"⚠️  日志文件不存在: {self.log_path}")
            return

        try:
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                # 先显示最后 N 行
                all_lines = f.readlines()
                for line in all_lines[-lines:]:
                    print(line.rstrip())

                if not follow:
                    return

                # 实时跟踪
                print("\n--- 开始实时监控 ---\n")
                f.seek(0, 2)  # 移动到文件末尾

                while True:
                    line = f.readline()
                    if line:
                        print(line.rstrip())

                        # 高亮显示错误
                        if 'Segmentation Fault' in line:
                            print("🔴 警告: 检测到段错误!")
                        elif 'error' in line.lower():
                            print("🟡 提示: 发现错误日志")
                    else:
                        time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n\n监控已停止")
        except Exception as e:
            print(f"❌ 读取日志时出错: {e}")

    def get_restart_command(self):
        """获取重启命令建议"""
        print("\n" + "=" * 60)
        print("重启命令参考")
        print("=" * 60)

        print("""
# 1. 优雅重启 (推荐)
# 向 master 进程发送 HUP 信号，worker 会逐个重启
kill -HUP <master_pid>

# 2. 完全重启
# 停止所有进程后重新启动
pkill -f uwsgi
uwsgi --ini uwsgi.ini

# 3. 使用宝塔面板
# 在宝塔面板的"Python项目管理器"中重启项目

# 4. 查看实时日志
# 在另一个终端运行:
tail -f /www/wwwlogs/python/beihuo_system/uwsgi.log
""")


def main():
    """主函数"""
    monitor = UWSGIMonitor()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == 'status':
            monitor.check_processes()
        elif command == 'logs':
            lines = int(sys.argv[2]) if len(sys.argv) > 2 else 100
            monitor.analyze_logs(lines)
        elif command == 'tail':
            lines = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            monitor.tail_logs(follow=True, lines=lines)
        elif command == 'restart':
            monitor.get_restart_command()
        else:
            print(f"未知命令: {command}")
            print_help()
    else:
        # 默认执行完整检查
        monitor.check_processes()
        monitor.analyze_logs()
        monitor.get_restart_command()


def print_help():
    """打印帮助信息"""
    print("""
用法: python scripts/monitor_uwsgi.py [命令] [参数]

命令:
    status          检查 uWSGI 进程状态
    logs [N]        分析最近 N 行日志 (默认 100)
    tail [N]        实时查看日志，先显示最后 N 行 (默认 20)
    restart         显示重启命令建议

示例:
    python scripts/monitor_uwsgi.py
    python scripts/monitor_uwsgi.py status
    python scripts/monitor_uwsgi.py logs 200
    python scripts/monitor_uwsgi.py tail
""")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        print_help()
    else:
        main()
