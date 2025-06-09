"""
极简版搜索智能体 - 使用MCP Tavily API执行搜索查询
"""
import asyncio
import os
from typing import Dict, Any, AsyncIterable
import json

from langchain_core.messages import AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import tool
from typing_extensions import TypedDict

# 电子邮件发送工具
@tool
def send_email(to: str, subject: str, body: str):
    """
    模拟发送电子邮件到指定收件人，注意收件人必须是用户输入的电子邮件地址。
    
    Args:
        to: 收件人电子邮件地址
        subject: 电子邮件主题
        body: 电子邮件正文内容
        
    Returns:
        包含发送状态的响应
    """
    print("*" * 40)
    print(f"模拟发送电子邮件到: {to}")
    print(f"主题: {subject}")
    print(f"内容: {body[:50]}{'...' if len(body) > 50 else ''}")
    print("*" * 40)
    
    # 模拟发送成功
    return {
        "success": True,
        "message": f"邮件已成功发送到 {to}"
    }

class SearchAgent:
    """SearchAgent - 专门用于搜索信息的助手"""

    SYSTEM_INSTRUCTION = '''
你是一个智能助手，会智能的使用工具来完成输入任务。
如果调用工具过程中需要用户提供参数信息，你必须严格按照以下格式返回JSON字符串，不要有任何解释:
{"status": "input-required", "message": "{需要用户提供的信息}"}
'''

    def __init__(self, model_name: str = "gpt-4o-mini"):
        """初始化搜索助手
        
        Args:
            model_name: 使用的LLM模型名称
        """
        self.model = ChatOpenAI(model=model_name)
        self._client = None
        self._agent = None
        # 初始化内存检查点保存器
        self.checkpointer = MemorySaver()

    async def _get_agent(self):
        
        if self._client is None:
            self._client = MultiServerMCPClient(
                {
                "tavily-mcp": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "tavily-mcp"
                    ],
                    "env": {
                        **os.environ
                    },
                    "transport": "stdio"
                }
                }
            )

            # 获取MCP工具
            mcp_tools = await self._client.get_tools()
            
            # 合并所有工具
            all_tools = mcp_tools + [send_email]
            print(f"SearchAgent可用工具: {[tool.name for tool in all_tools]}")

            # 创建agent with checkpointer
            self._agent = create_react_agent(
                self.model,
                tools=all_tools,
                prompt=self.SYSTEM_INSTRUCTION,
                checkpointer=self.checkpointer
            )
        return self._agent

    async def stream(self, query: str, context_id) -> AsyncIterable[Dict[str, Any]]:

        """流式调用智能体
            通过智能体异步流式处理消息列表，并根据不同类型的消息返回不同状态的响应。
            参数:
                messages (list): 消息列表，包含对话历史和当前查询
                    格式: [("user", "消息内容"), ("assistant", "回复内容"), ...]
                context_id: 对话上下文ID，用于保持会话连续性
            返回:
                AsyncIterable[Dict[str, Any]]: 异步迭代器，产生包含状态和内容的字典
                可能的状态包括:
                    - "working": 工具调用或处理过程中
                    - "input-required": 需要用户提供额外输入
                    - "completed": 处理完成
                    - "failed": 处理失败
            异常:
                捕获所有异常并以失败状态返回错误信息
        """
            
        agent = await self._get_agent()
        config = {'configurable': {'thread_id': context_id}}

        try:
            async for chunk in  agent.astream({"messages": [("user", query)]}, config=config, stream_mode='values'):
                message = chunk["messages"][-1]

                if (isinstance(message, AIMessage) and hasattr(message, "tool_calls") and message.tool_calls):
                    yield {"status":"working","content":f"正在调用工具【{message.tool_calls[0]["name"]}】..."}

                elif isinstance(message, ToolMessage):
                    yield {"status":"working","content":"正在处理工具调用结果..."}
            
                elif isinstance(message, AIMessage):
                    
                    if isinstance(message.content, str) and "input-required" in message.content:
                        try: 
                            input_info = json.loads(message.content)
                            yield {"status": "input-required", "content": input_info.get("message", "需要更多信息")}
                        except Exception as e:
                            yield {"status":"failed","content":str(e)}
                            pass
                    else:
                        yield {"status": "completed", "content": message.content}

        except Exception as e:

            yield {"status":"failed","content":str(e)}

    async def __aenter__(self):
        await self._get_agent()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        None

    async def get_conversation_history(self, context_id: str) -> list:
        """获取指定上下文的对话历史
        
        Args:
            context_id: 对话上下文ID
            
        Returns:
            对话历史消息列表
        """
        agent = await self._get_agent()
        config = {'configurable': {'thread_id': context_id}}
        
        try:
            state = await agent.aget_state(config)
            if state and hasattr(state, 'values') and 'messages' in state.values:
                return state.values['messages']
            return []
        except Exception as e:
            print(f"获取对话历史失败: {e}")
            return []

    async def clear_conversation_history(self, context_id: str) -> bool:
        """清除指定上下文的对话历史
        
        Args:
            context_id: 对话上下文ID
            
        Returns:
            操作是否成功
        """
        try:
            # 重置检查点状态
            config = {'configurable': {'thread_id': context_id}}
            agent = await self._get_agent()
            
            # 获取当前状态并清除消息
            state = await agent.aget_state(config)
            if state:
                # 更新状态为空消息列表
                await agent.aupdate_state(config, {"messages": []})
                print(f"已清除上下文 {context_id} 的对话历史")
                return True
            return False
        except Exception as e:
            print(f"清除对话历史失败: {e}")
            return False

    async def list_all_conversations(self) -> list:
        """列出所有保存的对话上下文
        
        Returns:
            对话上下文ID列表
        """
        try:
            # MemorySaver没有直接的方法列出所有键，这里返回空列表
            # 在实际应用中可以考虑使用其他类型的checkpointer如SqliteSaver
            print("当前使用的MemorySaver不支持列出所有对话")
            return []
        except Exception as e:
            print(f"列出对话失败: {e}")
            return []

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

async def main():
    """示例使用方法"""
    # 初始化搜索助手
    async with SearchAgent() as agent:
        
        # 测试循环与多次输入
        context_id = "conversation_1"  # 使用字符串作为上下文ID
        print("🤖 智能体已启动，支持对话历史保存")
        print("💡 输入'exit'退出对话，'clear'清除历史，'history'查看历史")
        
        while True:
            user_input = input("\n👤 请输入问题: ")
            
            if user_input.lower() == 'exit':
                break
            elif user_input.lower() == 'clear':
                # 清除对话历史
                success = await agent.clear_conversation_history(context_id)
                if success:
                    print("✅ 对话历史已清除")
                else:
                    print("❌ 清除对话历史失败")
                continue
            elif user_input.lower() == 'history':
                # 显示对话历史
                history = await agent.get_conversation_history(context_id)
                if history:
                    print("\n📜 ===== 对话历史 =====")
                    for idx, msg in enumerate(history):
                        role = getattr(msg, 'type', 'unknown')
                        content = getattr(msg, 'content', '')
                        print(f"[{idx}] {role}: {content[:100]}..." if len(str(content)) > 100 else f"[{idx}] {role}: {content}")
                    print("📜 ========================\n")
                else:
                    print("📝 暂无对话历史")
                continue
            
            print("\n⏳ 开始处理查询...")
            async for chunk in agent.stream(user_input, context_id=context_id):
                if chunk["status"] == "input-required":
                    print(f"🔍 {chunk}")

                    # 处理需要用户额外输入的情况
                    print(f"\n❓ 需要额外信息: {chunk['content']}")
                    additional_info = input("👤 请提供额外信息: ")

                    # 使用新的输入继续对话
                    async for response in agent.stream(additional_info, context_id=context_id):
                        print(f"🤖 {response}")
                else:
                    print(f"🤖 {chunk}")
            
            # 显示当前状态信息
            #print(f"\n💾 对话已保存到上下文: {context_id}")
            #print("📝 输入 'history' 查看完整对话历史")

if __name__ == "__main__":
    asyncio.run(main())
