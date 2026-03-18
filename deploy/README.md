# 服务化部署指南

## 前提条件

- 系统：Linux（systemd）
- 已完成虚拟环境创建和依赖安装（见 CLAUDE.md）
- 富途 OpenD 已运行

## 部署步骤

### 1. 编辑 service 文件，替换路径和用户

```bash
# 修改以下两行为实际值
# User=YOUR_USER
# WorkingDirectory=/path/to/code_quant
# ExecStart=/path/to/code_quant/env_quant/bin/python main.py sync
nano deploy/quant-sync.service
```

### 2. 安装 systemd unit 文件

```bash
sudo cp deploy/quant-sync.service /etc/systemd/system/

# 按需选择 timer（三市场精细触发 或 合并 timer）
# 方案A：三市场精细触发（推荐）
sudo cp deploy/quant-sync-a.timer  /etc/systemd/system/   # A股 16:30 北京时间
sudo cp deploy/quant-sync-hk.timer /etc/systemd/system/   # 港股 17:30 北京时间
sudo cp deploy/quant-sync-us.timer /etc/systemd/system/   # 美股 07:00 北京时间（次日）

# 方案B：合并 timer（仅 A股+港股，17:30 北京时间）
# sudo cp deploy/quant-sync.timer /etc/systemd/system/

sudo systemctl daemon-reload
```

### 3. 启用并启动定时器

```bash
# 方案A：启用三市场 timer
sudo systemctl enable quant-sync-a.timer quant-sync-hk.timer quant-sync-us.timer
sudo systemctl start  quant-sync-a.timer quant-sync-hk.timer quant-sync-us.timer

# 验证定时器状态和下次触发时间
sudo systemctl list-timers quant-sync-*.timer
```

### 4. 手动触发同步（测试用）

```bash
sudo systemctl start quant-sync.service

# 查看实时日志
sudo journalctl -u quant-sync.service -f
```

### 5. 查看健康状态

```bash
# health.json 由程序写入，包含最近一次同步状态
cat data/health.json
```

示例输出：
```json
{"status": "ok", "timestamp": "2026-03-18T10:30:00Z", "detail": "Sync completed for 3 stocks"}
```

状态值含义：
- `running`：正在同步中
- `ok`：上次同步成功
- `error`：上次同步失败（detail 包含错误信息）
- `stopped`：被 SIGTERM/KeyboardInterrupt 中断
- `idle`：watchlist 无活跃股票

### 6. 停止服务（优雅退出）

```bash
# 发送 SIGTERM，等待当前任务完成（最多 300s）
sudo systemctl stop quant-sync.service
```

## 手动运行命令

```bash
# 同步（默认）
python main.py sync
python main.py          # 等价于 sync

# 导出数据
python main.py export SH.600519 1D 2024-01-01 2024-12-31
python main.py export SH.600519 1D 2024-01-01 2024-12-31 --adj-type raw --fmt csv

# 查看同步状态
python main.py stats
```
