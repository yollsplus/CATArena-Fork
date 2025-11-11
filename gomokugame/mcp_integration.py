#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP (Model Context Protocol) 集成模块

使用 Anthropic 官方的 MCP 协议与文件系统服务器通信，
提供安全的文件读写能力给 LLM Agent。
"""

import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPFileSystemClient:
    """MCP 文件系统客户端，封装与 MCP 服务器的交互"""
    
    def __init__(self, workspace_root: Path, allowed_paths: Optional[List[str]] = None):
        """
        初始化 MCP 客户端
        
        Args:
            workspace_root: 工作空间根目录（gomokugame 目录）
            allowed_paths: 允许访问的路径列表（相对于 workspace_root）
                         默认只允许访问 ./develop_ai 和 ./gomoku
        """
        self.workspace_root = Path(workspace_root).resolve()
        
        # 只读路径：可以读取，但不能写入/修改/删除
        self.readonly_paths = [
            str(self.workspace_root / "./gomoku/README.md"),
            str(self.workspace_root / "./gomoku/develop_instruction.md"),
            str(self.workspace_root / "./gomoku/AI_example"),  # 示例代码（只读）
        ]
        
        # 读写路径：可以完全访问
        self.readwrite_paths = [
            str(self.workspace_root / "./gomoku/AI_develop"),  # Agent 开发目录（可写）
        ]
        
        # 兼容旧接口
        if allowed_paths is None:
            self.allowed_paths = self.readonly_paths + self.readwrite_paths
        else:
            self.allowed_paths = [str(self.workspace_root / p) for p in allowed_paths]
        
        # MCP 服务器参数
        self.server_params = StdioServerParameters(
            command="npx",
            args=[
                "-y",
                "@modelcontextprotocol/server-filesystem",
                str(self.workspace_root)
            ],
            env=None
        )
        
        self.session: Optional[ClientSession] = None
        self.available_tools: List[Dict[str, Any]] = []
    
    @asynccontextmanager
    async def connect(self):
        """连接到 MCP 服务器（上下文管理器）"""
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # 初始化会话
                await session.initialize()
                
                # 列出可用工具
                tools_result = await session.list_tools()
                self.available_tools = tools_result.tools if hasattr(tools_result, 'tools') else []
                
                print(f"[MCP] 连接成功，可用工具: {[t.name for t in self.available_tools]}")
                
                self.session = session
                yield self
                self.session = None
    
    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """
        获取适配 OpenAI/Anthropic function calling 格式的工具定义
        
        Returns:
            工具定义列表（JSON Schema 格式）
        """
        tools = []
        
        for tool in self.available_tools:
            # 转换 MCP 工具定义为 OpenAI function calling 格式
            tool_def = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or f"MCP tool: {tool.name}",
                    "parameters": tool.inputSchema if hasattr(tool, 'inputSchema') else {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
            tools.append(tool_def)
        
        return tools
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        调用 MCP 工具
        
        Args:
            tool_name: 工具名称（如 read_file, write_file）
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        if not self.session:
            raise RuntimeError("MCP session not connected. Use 'async with client.connect():'")
        
        # 写操作工具列表
        write_operations = ['write_file', 'edit_file', 'create_directory', 'move_file', 'delete_file']
        
        # 安全检查：验证路径在允许范围内
        if 'path' in arguments:
            requested_path = Path(arguments['path']).resolve()
            
            # 检查写操作权限
            if tool_name in write_operations:
                if not self._is_path_writable(requested_path):
                    return {
                        "error": f"Write access denied: {requested_path} is read-only",
                        "writable_paths": self.readwrite_paths
                    }
            else:
                # 读操作只需要在允许列表中
                if not self._is_path_allowed(requested_path):
                    return {
                        "error": f"Access denied: {requested_path} is outside allowed paths",
                        "allowed_paths": self.allowed_paths
                    }
        
        # move_file 特殊处理：source 和 destination 都要检查
        if tool_name == 'move_file':
            if 'source' in arguments:
                source_path = Path(arguments['source']).resolve()
                if not self._is_path_writable(source_path):
                    return {
                        "error": f"Move denied: source {source_path} is read-only",
                        "writable_paths": self.readwrite_paths
                    }
            if 'destination' in arguments:
                dest_path = Path(arguments['destination']).resolve()
                if not self._is_path_writable(dest_path):
                    return {
                        "error": f"Move denied: destination {dest_path} is read-only",
                        "writable_paths": self.readwrite_paths
                    }
        
        try:
            result = await self.session.call_tool(tool_name, arguments=arguments)
            
            # 解析结果
            if hasattr(result, 'content'):
                # MCP 返回的是 content 数组
                content_parts = []
                for item in result.content:
                    if hasattr(item, 'text'):
                        content_parts.append(item.text)
                    elif hasattr(item, 'data'):
                        content_parts.append(str(item.data))
                
                return {
                    "success": True,
                    "content": "\n".join(content_parts)
                }
            else:
                return {
                    "success": True,
                    "result": str(result)
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _is_path_allowed(self, path: Path) -> bool:
        """检查路径是否在允许访问的范围内（读取权限）"""
        path_str = str(path)
        
        for allowed in self.allowed_paths:
            allowed_path = Path(allowed).resolve()
            
            # 检查是否是允许路径的子路径
            try:
                path.relative_to(allowed_path)
                return True
            except ValueError:
                # 检查是否是精确匹配（对于文件）
                if path == allowed_path:
                    return True
                continue
        
        return False
    
    def _is_path_writable(self, path: Path) -> bool:
        """检查路径是否可写（写入/修改/删除权限）"""
        for writable in self.readwrite_paths:
            writable_path = Path(writable).resolve()
            
            # 检查是否是可写路径的子路径
            try:
                path.relative_to(writable_path)
                return True
            except ValueError:
                # 检查是否是精确匹配
                if path == writable_path:
                    return True
                continue
        
        return False


class MCPAgentRunner:
    """使用 MCP 运行 Agent 的工具类"""
    
    def __init__(self, api_key: str, api_url: str, model: str, workspace_root: Path):
        """
        初始化 Agent Runner
        
        Args:
            api_key: API 密钥
            api_url: API 端点 URL
            model: 模型名称
            workspace_root: 工作空间根目录
        """
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.workspace_root = workspace_root
        
        self.mcp_client = MCPFileSystemClient(workspace_root)
    
    async def run_agent_with_mcp(self, prompt: str, max_iterations: int = 15) -> Dict[str, Any]:
        """
        运行 Agent，支持 MCP 工具调用
        
        Args:
            prompt: 用户提示词
            max_iterations: 最大工具调用迭代次数
            
        Returns:
            Agent 响应结果
        """
        async with self.mcp_client.connect():
            # 根据 API 类型选择不同的客户端
            if "anthropic" in self.api_url.lower() or self.model.startswith("claude"):
                return await self._run_with_anthropic(prompt, max_iterations)
            else:
                return await self._run_with_openai(prompt, max_iterations)
    
    async def _run_with_openai(self, prompt: str, max_iterations: int) -> Dict[str, Any]:
        """使用 OpenAI API 运行（兼容格式）"""
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(api_key=self.api_key, base_url=self.api_url)
        
        messages = [{"role": "user", "content": prompt}]
        tools = self.mcp_client.get_tools_for_llm()
        
        for iteration in range(max_iterations):
            print(f"\n[Agent] 迭代 {iteration + 1}/{max_iterations}")
            
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            message = response.choices[0].message
            
            # 如果没有工具调用，返回结果
            if not message.tool_calls:
                return {
                    "content": message.content,
                    "model": self.model,
                    "usage": response.usage._asdict() if response.usage else {},
                    "iterations": iteration + 1
                }
            
            # 执行工具调用
            messages.append(message)
            
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                print(f"  - 调用工具: {tool_name}({tool_args})")
                
                # 通过 MCP 调用工具
                result = await self.mcp_client.call_tool(tool_name, tool_args)
                
                # 添加工具响应到消息历史
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False)
                })
        
        # 达到最大迭代次数
        return {
            "content": "达到最大工具调用次数",
            "model": self.model,
            "iterations": max_iterations,
            "warning": "max_iterations_reached"
        }
    
    async def _run_with_anthropic(self, prompt: str, max_iterations: int) -> Dict[str, Any]:
        """使用 Anthropic Claude API 运行"""
        import anthropic
        
        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        
        messages = [{"role": "user", "content": prompt}]
        tools = self._convert_tools_for_anthropic()
        
        for iteration in range(max_iterations):
            print(f"\n[Agent] 迭代 {iteration + 1}/{max_iterations}")
            
            response = await client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=messages,
                tools=tools
            )
            
            # 检查是否有工具调用
            tool_calls = [block for block in response.content if block.type == "tool_use"]
            
            if not tool_calls:
                # 没有工具调用，返回文本响应
                text_content = "".join([
                    block.text for block in response.content if block.type == "text"
                ])
                
                return {
                    "content": text_content,
                    "model": self.model,
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens
                    },
                    "iterations": iteration + 1
                }
            
            # 添加 assistant 消息
            messages.append({"role": "assistant", "content": response.content})
            
            # 执行工具调用
            tool_results = []
            for tool_use in tool_calls:
                tool_name = tool_use.name
                tool_args = tool_use.input
                
                print(f"  - 调用工具: {tool_name}({tool_args})")
                
                # 通过 MCP 调用工具
                result = await self.mcp_client.call_tool(tool_name, tool_args)
                
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result, ensure_ascii=False)
                })
            
            # 添加工具结果
            messages.append({"role": "user", "content": tool_results})
        
        # 达到最大迭代次数
        return {
            "content": "达到最大工具调用次数",
            "model": self.model,
            "iterations": max_iterations,
            "warning": "max_iterations_reached"
        }
    
    def _convert_tools_for_anthropic(self) -> List[Dict[str, Any]]:
        """转换工具定义为 Anthropic 格式"""
        anthropic_tools = []
        
        for tool in self.mcp_client.available_tools:
            anthropic_tools.append({
                "name": tool.name,
                "description": tool.description or f"MCP tool: {tool.name}",
                "input_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            })
        
        return anthropic_tools


# 同步包装器（用于兼容现有代码）
def run_agent_with_mcp_sync(
    prompt: str,
    api_key: str,
    api_url: str,
    model: str,
    workspace_root: Path,
    max_iterations: int = 15
) -> Dict[str, Any]:
    """
    同步版本的 Agent 运行器（内部使用 asyncio）
    
    Args:
        prompt: 用户提示词
        api_key: API 密钥
        api_url: API 端点
        model: 模型名称
        workspace_root: 工作空间根目录
        max_iterations: 最大迭代次数
        
    Returns:
        Agent 响应结果
    """
    runner = MCPAgentRunner(api_key, api_url, model, workspace_root)
    
    # 在新的事件循环中运行
    return asyncio.run(runner.run_agent_with_mcp(prompt, max_iterations))
