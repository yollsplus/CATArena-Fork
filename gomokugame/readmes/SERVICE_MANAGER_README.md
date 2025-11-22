# 服务自动管理功能

## 功能说明

现在 `auto_iteration_manager.py` 已经集成了自动服务管理功能！🎉

### 新增的功能

1. **自动启动游戏服务器** - 不再需要手动运行 `bash start_server.sh`
2. **自动启动所有 AI 服务** - 根据配置文件自动启动所有 AI
3. **健康检查** - 自动检测服务是否启动成功
4. **自动清理** - 程序结束时自动停止所有服务

---

## 使用方法

### 方法 1: 使用 auto_iteration_manager（推荐）

直接运行完整的迭代流程，服务会自动管理：

```bash
python auto_iteration_manager.py --config my_config.json
```

**流程：**
1. 生成 Prompt
2. 调用 Agent (MCP)
3. 部署代码
4. **自动启动游戏服务器** ✨
5. **自动启动所有 AI 服务** ✨
6. 运行对战
7. **自动清理所有服务** ✨

---

### 方法 2: 测试服务管理器

如果只想测试服务启动功能：

```bash
python test_service_manager.py
```

这会：
- 启动游戏服务器（端口 9000）
- 启动 demo1 (端口 12001)
- 启动 demo2 (端口 12002)
- 启动 gpt-4o-mini_ai_v1 (端口 12003)
- 等待你按 Enter 键后自动清理

---

## 技术细节

### ServiceManager 类

```python
class ServiceManager:
    def start_game_server(self, game='gomoku', port=9000)
    def start_ai_service(self, ai_path, port, ai_name)
    def cleanup()  # 自动清理所有进程
```

**特性：**
- ✅ 跨平台支持（Windows/Linux/Mac）
- ✅ 健康检查（等待服务就绪）
- ✅ 自动清理（atexit 注册）
- ✅ 超时控制（避免无限等待）
- ✅ Windows 进程组管理（优雅停止）

---

## 配置要求

确保你的 `round_1_config.json` 配置正确：

```json
{
  "game_server": {
    "url": "http://localhost:9000",
    "timeout": 10
  },
  "ais": [
    {
      "ai_id": "demo1",
      "ai_name": "Demo 1",
      "port": 12001
    },
    {
      "ai_id": "demo2",
      "ai_name": "Demo 2",
      "port": 12002
    },
    {
      "ai_id": "gpt-4o-mini_ai_v1",
      "ai_name": "GPT-4o-mini AI v1",
      "port": 12003
    }
  ]
}
```

---

## 常见问题

### Q: 服务启动超时怎么办？
A: 
- 检查端口是否被占用
- 增加超时时间（在代码中修改 `timeout` 参数）
- 检查 `ai_service.py` 是否支持 `--port` 参数

### Q: 如何手动清理进程？
A: 
程序会自动清理，但如果需要手动清理：
```bash
# Windows
taskkill /F /IM python.exe

# Linux/Mac
pkill -f "python.*server.py"
pkill -f "python.*ai_service.py"
```

### Q: 可以同时运行多个 Round 吗？
A: 
不建议，因为会端口冲突。建议：
1. 运行完一个 Round
2. 等待自动清理
3. 再运行下一个 Round

---

## 注意事项

1. **端口冲突** - 确保配置的端口没有被占用
2. **路径问题** - AI 代码必须在 `AI_competitors/gomoku/round_X/` 目录下
3. **健康检查** - 确保所有服务都实现了 `/health` 端点
4. **依赖安装** - 需要 `requests` 库: `pip install requests`

---

## 优势对比

| 功能 | 手动启动 | 自动管理 |
|------|---------|---------|
| 启动游戏服务器 | ❌ 需要手动 | ✅ 自动 |
| 启动 AI 服务 | ❌ 每个都要手动 | ✅ 自动 |
| 健康检查 | ❌ 需要自己检查 | ✅ 自动 |
| 清理进程 | ❌ 需要手动 kill | ✅ 自动 |
| 多终端管理 | ❌ 需要 4+ 个终端 | ✅ 只需 1 个 |
| 错误处理 | ❌ 手动处理 | ✅ 自动重试/报错 |

---

## 下一步

现在你可以：

1. **测试服务管理** - 运行 `python test_service_manager.py`
2. **运行完整流程** - 运行 `python auto_iteration_manager.py --config my_config.json`
3. **检查日志** - 查看 `auto_iteration_output/` 目录

享受全自动化的评测流程！🚀
