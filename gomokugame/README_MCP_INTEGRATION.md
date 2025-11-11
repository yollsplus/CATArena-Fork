# MCP (Model Context Protocol) 集成文档

## 概述

本项目已从手写 ADK 迁移到 **Anthropic 官方的 MCP (Model Context Protocol)** 标准，实现更规范、安全的 Agent 文件访问能力。

---

## 安装依赖

### 1. Python 依赖

```bash
cd gomokugame
pip install mcp anthropic openai
```

### 2. Node.js MCP 文件系统服务器

MCP 文件系统服务器使用 Node.js 实现，需要先安装 Node.js（如果还没有）。

**安装 MCP 文件系统服务器：**

```bash
npm install -g @modelcontextprotocol/server-filesystem
```

**或者在首次运行时自动安装（使用 `npx`）：**

脚本会自动使用 `npx -y @modelcontextprotocol/server-filesystem`，会在首次运行时自动下载。

### 3. 验证安装

```bash
# 验证 Python 包
python -c "import mcp; print('MCP installed')"

# 验证 Node.js 和 npx
npx -v

# 验证 MCP 文件系统服务器
npx @modelcontextprotocol/server-filesystem --help
```

---

## 配置说明

### my_config.json

```json
{
  "game": "gomoku",
  "agent": {
    "type": "openai",  // 或 "anthropic"
    "api_key": "your-api-key",
    "model": "gpt-4o-mini",  // 或 "claude-3-5-sonnet-20241022"
    "base_url": "https://api.openai.com/v1",  // OpenAI 兼容 API
    "use_mcp": true,  // 启用 MCP 工具调用
    "mcp_max_iterations": 15  // 最大工具调用迭代次数
  },
  "iteration": {
    "max_rounds": 3,
    "use_llm_summary": true,
    "llm_summary_config": {
      "api_url": "https://api.openai.com/v1/chat/completions",
      "api_key": "your-api-key",
      "model": "gpt-4o-mini"
    }
  }
}
```

**关键配置项：**

- **`use_mcp`**: `true` 启用 MCP，Agent 可以调用文件读写工具
- **`mcp_max_iterations`**: 最大工具调用次数（防止无限循环）
- **`type`**: 支持 `"openai"` 和 `"anthropic"`

---

## MCP 工具能力

当 `use_mcp=true` 时，Agent 可以使用以下工具：

### 文件系统工具（来自 `@modelcontextprotocol/server-filesystem`）

1. **`read_file`** - 读取文件内容
   ```json
   {
     "path": "./gomoku/README.md"
   }
   ```

2. **`write_file`** - 写入文件
   ```json
   {
     "path": "./develop_ai/ai_service.py",
     "content": "<Python code here>"
   }
   ```

3. **`list_directory`** - 列出目录内容
   ```json
   {
     "path": "./gomoku"
   }
   ```

4. **`create_directory`** - 创建目录
   ```json
   {
     "path": "./develop_ai/utils"
   }
   ```

5. **`move_file`** - 移动/重命名文件
6. **`search_files`** - 搜索文件内容
7. 等等...

### 安全限制

**允许访问的路径（白名单）：**
- `./develop_ai/` - Agent 开发目录
- `./gomoku/README.md` - 游戏文档
- `./gomoku/develop_instruction.md` - 开发指南

**禁止访问：**
- 工作空间外的路径（如 `C:\Windows`）
- 敏感文件（如 `my_config.json`）
- Arena 配置和日志

路径验证在 `mcp_integration.py` 的 `MCPFileSystemClient._is_path_allowed()` 中实现。

---

## 使用示例

### 基本用法

```python
from mcp_integration import run_agent_with_mcp_sync

response = run_agent_with_mcp_sync(
    prompt="Read ./gomoku/README.md and create a Gomoku AI in ./develop_ai/",
    api_key="your-api-key",
    api_url="https://api.openai.com/v1",
    model="gpt-4o-mini",
    workspace_root="./gomokugame",
    max_iterations=15
)

print(response['content'])
```

### Agent 工作流示例

**用户提示词：**
```
Read the game rules from ./gomoku/README.md and ./gomoku/develop_instruction.md,
then create a competitive Gomoku AI service in ./develop_ai/ai_service.py
with a start script ./develop_ai/start_ai.sh
```

**Agent 执行过程：**

1. **调用 `list_directory`** - 查看 `./gomoku` 目录结构
2. **调用 `read_file`** - 读取 `./gomoku/README.md`
3. **调用 `read_file`** - 读取 `./gomoku/develop_instruction.md`
4. **调用 `write_file`** - 创建 `./develop_ai/ai_service.py`（完整 Python 代码）
5. **调用 `write_file`** - 创建 `./develop_ai/start_ai.sh`（启动脚本）
6. **返回最终响应** - "AI service created successfully..."

---

## 架构说明

### 文件结构

```
gomokugame/
├── mcp_integration.py          # MCP 集成模块
├── auto_iteration_manager.py   # 主控制器（使用 MCP）
├── my_config.json              # 配置文件（use_mcp=true）
└── develop_ai/                 # Agent 输出目录
    ├── ai_service.py           # Agent 生成的 AI 代码
    └── start_ai.sh             # Agent 生成的启动脚本
```

### MCP 通信流程

```
┌──────────────────┐
│ auto_iteration_  │
│    manager.py    │
└────────┬─────────┘
         │
         │ run_agent_with_mcp_sync()
         ▼
┌──────────────────┐
│  mcp_integration │
│      .py         │
│  MCPAgentRunner  │
└────────┬─────────┘
         │
         │ OpenAI/Anthropic API + Tools
         ▼
┌──────────────────┐       ┌──────────────────┐
│   LLM (GPT-4/   │◄─────►│   MCP Filesystem │
│   Claude-3.5)   │  MCP  │     Server       │
└──────────────────┘       │  (Node.js npx)   │
                           └────────┬─────────┘
                                    │
                                    │ 文件读写
                                    ▼
                           ┌──────────────────┐
                           │   ./develop_ai/  │
                           │   ./gomoku/      │
                           └──────────────────┘
```

### 关键类

**`MCPFileSystemClient`** (`mcp_integration.py`)
- 管理与 MCP 文件系统服务器的连接
- 提供工具定义转换（MCP → OpenAI/Anthropic 格式）
- 实现路径安全检查

**`MCPAgentRunner`** (`mcp_integration.py`)
- 运行支持 MCP 的 Agent
- 处理多轮工具调用迭代
- 支持 OpenAI 和 Anthropic API

---

## 与旧 ADK 的对比

| 特性 | 手写 ADK (simple_adk.py) | MCP 集成 |
|------|-------------------------|----------|
| **协议标准** | 自定义 | Anthropic 官方标准 |
| **工具生态** | 手动实现 | 丰富的官方/社区工具 |
| **安全性** | 手动实现 | 内置沙箱和权限控制 |
| **可维护性** | 需自行维护 | 官方维护 + 社区支持 |
| **功能丰富度** | read_file, list_directory | read/write/move/search/create... |
| **跨语言支持** | Python only | Python/TypeScript/Rust |
| **学习成本** | 低（简单代码） | 中（需了解 MCP 协议） |
| **未来扩展** | 手动添加功能 | 直接使用新 MCP 服务器 |

---

## 故障排除

### 1. MCP 服务器无法启动

**错误：**
```
Error: Cannot find module '@modelcontextprotocol/server-filesystem'
```

**解决：**
```bash
npm install -g @modelcontextprotocol/server-filesystem
```

或确保 `npx` 可用（会自动下载）。

### 2. 路径访问被拒绝

**错误：**
```json
{
  "error": "Access denied: /some/path is outside allowed paths"
}
```

**解决：**  
修改 `mcp_integration.py` 中的 `MCPFileSystemClient.__init__()` 的 `allowed_paths` 列表。

### 3. Agent 不调用工具

**可能原因：**
- `use_mcp=false` 在配置中
- 提示词不够明确（Agent 没理解需要读文件）
- 模型不支持 function calling（确保使用 gpt-4/gpt-4o/claude-3.5）

**解决：**
- 确认 `my_config.json` 中 `use_mcp: true`
- 提示词明确说明 "Read file XXX and write to YYY"
- 使用支持工具调用的模型

### 4. 工具调用次数耗尽

**错误：**
```json
{
  "warning": "max_iterations_reached"
}
```

**解决：**  
增加 `mcp_max_iterations` 值（如 20 或 30）。

---

## 最佳实践

### 1. 提示词设计

**好的提示词（明确文件操作）：**
```
1. Read ./gomoku/README.md to understand the game rules
2. Read ./gomoku/develop_instruction.md for API specification
3. Create a competitive AI in ./develop_ai/ai_service.py
4. Create a start script in ./develop_ai/start_ai.sh
```

**不好的提示词（模糊）：**
```
Make a Gomoku AI
```

### 2. 安全配置

- 只在 `allowed_paths` 中添加必要的目录
- 不要允许访问配置文件（如 `my_config.json`）
- 定期审查 Agent 生成的代码

### 3. 性能优化

- 使用 `mcp_max_iterations` 限制工具调用次数
- 对于简单任务，可以设置 `use_mcp=false` 禁用工具调用
- 使用更快的模型（如 gpt-4o-mini）降低延迟

---

## 下一步计划

- [ ] 添加更多 MCP 服务器（Git、Database、HTTP）
- [ ] 实现代码自动验证（语法检查、测试运行）
- [ ] 增强安全审计日志
- [ ] 支持多 Agent 协作（通过 MCP 共享上下文）

---

## 参考资源

- **MCP 官方文档**: https://modelcontextprotocol.io
- **MCP GitHub**: https://github.com/modelcontextprotocol
- **MCP Python SDK**: https://github.com/modelcontextprotocol/python-sdk
- **MCP 服务器列表**: https://github.com/modelcontextprotocol/servers

---

**更新时间**: 2025-11-07  
**版本**: v2.0（MCP 集成版本）
