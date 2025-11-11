# 自动化迭代管理器使用指南

## 📋 功能说明

`auto_iteration_manager.py` 是一个自动化脚本，用于管理 CATArena 的多轮评测流程。

### 主要功能

1. **自动生成提示词**
   - Round 1: 使用 `ChatPrompt.py` 生成基础提示词
   - Round 2+: 使用 `ChatPromptWithLlm.py` 分析上轮日志并生成增强提示词

2. **自动发送给Agent**
   - 支持 OpenAI API (GPT-4, GPT-3.5等)
   - 支持 Anthropic API (Claude)
   - 支持自定义API

3. **自动运行对战**
   - 启动AI服务
   - 运行竞技场对战
   - 收集对战报告

4. **记录评测数据**
   - 每轮的提示词
   - Agent的响应
   - 对战结果
   - 生成最终评测报告

---

## 🚀 快速开始

### 1. 安装依赖

```bash
# 如果使用 OpenAI
pip install openai

# 如果使用 Anthropic
pip install anthropic

# 如果使用自定义API
pip install requests
```

### 2. 创建配置文件

复制示例配置并修改：

```bash
cp auto_config_example.json my_config.json
```

编辑 `my_config.json`，填入你的API密钥：

```json
{
  "game": "gomoku",
  "agent": {
    "type": "openai",
    "api_key": "sk-your-actual-key",
    "model": "gpt-4"
  },
  "iteration": {
    "max_rounds": 3,
    "use_llm_summary": true,
    "llm_summary_config": {
      "api_key": "sk-your-actual-key"
    }
  }
}
```

### 3. 运行自动化流程

```bash
cd gomokugame
python auto_iteration_manager.py --config my_config.json
```

---

## 📖 详细流程

### 每一轮的执行步骤

```
[1/6] 生成提示词
      ↓
[2/6] 保存提示词到文件
      ↓
[3/6] 发送给Agent API
      ↓
[4/6] 保存Agent响应
      ↓
[5/6] 等待用户部署代码 ⚠️ 需要人工介入
      ↓
[6/6] 运行对战并记录结果
```

### ⚠️ 人工介入步骤

脚本会在每轮发送提示词给Agent后**暂停**，等待你：

1. 查看Agent的响应（保存在 `auto_iteration_output/round_N_agent_response.json`）
2. 从响应中提取代码
3. 部署到 `AI_competitors/gomoku/round_N/<your_ai>/`
4. 按 Enter 继续运行对战

---

## 📁 输出文件

所有输出保存在 `auto_iteration_output/` 目录：

```
auto_iteration_output/
├── round_1_prompt.txt              # Round 1 提示词
├── round_1_agent_response.json     # Round 1 Agent响应
├── round_2_prompt.txt              # Round 2 提示词
├── round_2_agent_response.json     # Round 2 Agent响应
├── ...
├── iteration_log.json              # 迭代日志
└── final_report.json               # 最终评测报告
```

---

## 🔧 配置选项详解

### Agent配置

#### OpenAI
```json
{
  "agent": {
    "type": "openai",
    "api_key": "sk-xxx",
    "model": "gpt-4",
    "base_url": "https://api.openai.com/v1"  // 可选，用于自定义端点
  }
}
```

#### Anthropic (Claude)
```json
{
  "agent": {
    "type": "anthropic",
    "api_key": "sk-ant-xxx",
    "model": "claude-3-opus-20240229"
  }
}
```

#### 自定义API
```json
{
  "agent": {
    "type": "custom",
    "api_url": "http://your-api.com/generate",
    "api_key": "your-key",
    "headers": {
      "Custom-Header": "value"
    },
    "payload_template": {
      "temperature": 0.7,
      "max_tokens": 8000
    }
  }
}
```

### 迭代配置

```json
{
  "iteration": {
    "max_rounds": 5,                // 最多运行5轮
    "use_llm_summary": true,        // 使用LLM分析上轮日志
    "llm_summary_config": {
      "api_url": "https://api.openai.com/v1/chat/completions",
      "api_key": "sk-xxx",
      "model": "gpt-4o-mini"        // 用于分析日志的模型
    }
  }
}
```

---

## 💡 使用技巧

### 1. 只运行部分轮次

```bash
python auto_iteration_manager.py --config my_config.json --rounds 2
```

### 2. 跳过对战

如果代码还没准备好，可以在提示时输入 `skip` 跳过本轮对战：

```
代码部署完成后，按 Enter 继续运行 Round 1 对战，或输入 'skip' 跳过对战: skip
```

### 3. 查看Agent响应

```bash
# 查看Round 1的Agent响应
cat auto_iteration_output/round_1_agent_response.json
```

### 4. 从Agent响应中提取代码

Agent的响应通常包含代码块，你需要手动提取并保存为文件。未来版本会自动化这一步。
