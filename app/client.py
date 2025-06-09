"""
通用A2A智能体客户端
- 支持流式响应
- 支持推送通知
- 友好的中文输出
"""
import asyncio
import logging
import sys
import pathlib
from typing import Any, Dict, Optional, Tuple, Union
from uuid import uuid4
import urllib.parse
import base64
import os
import threading
import json

# 添加父目录到Python路径，使app模块可以被正确导入
current_dir = pathlib.Path(__file__).parent.absolute()
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import asyncclick as click
import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response

from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    MessageSendParams,
    Part,
    SendStreamingMessageRequest,
    SendMessageRequest,
    TextPart,
    FilePart,
    FileWithBytes,
    Task,
    TaskState,
    Message,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    MessageSendConfiguration,
    JSONRPCErrorResponse,
    GetTaskRequest,
    TaskQueryParams, 
    GetTaskResponse,
    GetTaskSuccessResponse,
    PushNotificationConfig
)
from dotenv import load_dotenv


load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def display_message(message: Message) -> None:
    """友好地展示消息对象的详细信息

    Args:
        message: 消息对象
    """
    print("\n" + "=" * 60)
    print("💬 消息信息【类型：Message】")
    print("=" * 60)
    print(f"🆔 消息ID: {message.messageId}")
    print(f"📌 上下文ID: {message.contextId}") 
    print(f"🆔 任务ID: {message.taskId}")
    print(f"👤 角色: {message.role}")
    print("📝 消息内容:")
    for part in message.parts:
        if hasattr(part.root, 'text') and part.root.text:
            print(f"  {part.root.text}")
        elif hasattr(part.root, 'file') and isinstance(part.root.file, FileWithBytes):
            file_name = part.root.file.name if part.root.file.name else "未命名文件"
            print(f"  📎 包含文件: {file_name}")
        else:
            print(f"  未知内容: {part.model_dump_json(exclude_none=True)}")

def display_task(task: Task) -> None:
    """友好地展示任务对象的详细信息
    
    Args:
        task: 任务对象
    """
    print("\n" + "=" * 60)
    print("📋 任务信息【类型：Task】")
    print("=" * 60)
    
    # 显示任务ID
    print(f"🆔 任务ID: {task.id}")
    
    # 显示上下文ID
    if hasattr(task, 'contextId'):
        print(f"📌 上下文ID: {task.contextId}")
    
    # 显示任务状态
    if hasattr(task, 'status') and hasattr(task.status, 'state'):
        state = task.status.state
        state_emoji = {
            "submitted": "📤",
            "working": "⚙️",
            "input-required": "❓",
            "completed": "✅",
            "canceled": "🛑",
            "failed": "❌", 
            "rejected": "⛔",
            "auth-required": "🔒",
            "unknown": "❔",
            # 为兼容性保留一些旧状态
            "thinking": "🤔",
            "error": "⚠️",
        }.get(state, "🔄")
        print(f"{state_emoji} 状态: {state}")

        # 显示状态消息内容
        if hasattr(task.status, 'message') and task.status.message:
            message = task.status.message
            print("\n📝 状态消息:")
            if hasattr(message, 'parts'):
                for part in message.parts:
                    if hasattr(part, 'root') and hasattr(part.root, 'text'):
                        print(f"  {part.root.text}")
                    elif hasattr(part, 'text'):
                        print(f"  {part.text}")
    
    # 显示历史消息
    if hasattr(task, 'history') and task.history:
        print("\n📜 历史消息:")
        for msg in task.history:
            # 处理role可能是对象或字符串的情况
            role_str = str(msg.role)
            role_emoji = "👤" if role_str == "user" else "🤖"
            print(f"\n{role_emoji} {role_str.upper()}:")
            for part in msg.parts:
                if hasattr(part, 'text'):
                    print(f"  {part.text}")
                elif hasattr(part, 'root') and hasattr(part.root, 'text'):
                    print(f"  {part.root.text}")

    # 显示工件信息
    if hasattr(task, 'artifacts') and task.artifacts:
        print("\n📦 工件信息:")
        for artifact in task.artifacts:
            artifact_name = artifact.name if hasattr(artifact, 'name') else "未命名"
            print(f"  工件名称: {artifact_name}")
            if hasattr(artifact, 'artifactId'):
                print(f"  工件ID: {artifact.artifactId}")
            if hasattr(artifact, 'parts'):
                print("  工件内容:")
                for part in artifact.parts:
                    if hasattr(part, 'text'):
                        print(f"    {part.text}")
                    elif hasattr(part, 'root') and hasattr(part.root, 'text'):
                        print(f"    {part.root.text}")
                    elif hasattr(part, 'kind') and part.kind == "file":
                        print("    📎 包含文件附件")
    
def display_task_status_update(status_event: TaskStatusUpdateEvent) -> None:
    """友好地展示任务状态更新的详细信息
    
    Args:
        status_event: 任务状态更新事件
    """
    print("\n" + "=" * 60)
    print("📊 任务状态更新【类型：TaskStatusUpdateEvent】")
    print("=" * 60)
    
    # 获取状态
    state = status_event.status.state if hasattr(status_event.status, 'state') else "unknown"
    
    # 状态对应的表情
    state_emoji = {
        "submitted": "📤",
        "working": "⚙️",
        "input-required": "❓",
        "completed": "✅",
        "canceled": "🛑",
        "failed": "❌", 
        "rejected": "⛔",
        "auth-required": "🔒",
        "unknown": "❔",
        # 为兼容性保留一些旧状态
        "thinking": "🤔",
        "error": "⚠️",
    }.get(state, "🔄")
    
    print(f"{state_emoji} 状态: {state}")
    
    # 显示消息内容（如果有）
    if hasattr(status_event.status, 'message') and status_event.status.message:
        message = status_event.status.message
        if hasattr(message, 'parts'):
            for part in message.parts:
                if hasattr(part, 'root') and hasattr(part.root, 'text'):
                    print(f"📝 消息: {part.root.text}")
                elif hasattr(part, 'text'):
                    print(f"📝 消息: {part.text}")
    
    # 是否是最终状态
    if hasattr(status_event, 'final') and status_event.final:
        print("🏁 这是最终状态")

def display_artifact_update(artifact_event: TaskArtifactUpdateEvent) -> None:
    """友好地展示任务工件更新的详细信息
    
    Args:
        artifact_event: 任务工件更新事件
    """
    print("\n" + "=" * 60)
    print("📦 任务工件更新【类型：TaskArtifactUpdateEvent】")
    print("=" * 60)
    
    # 显示工件名称
    artifact_name = artifact_event.artifact.name if hasattr(artifact_event.artifact, 'name') else "未命名"
    print(f"📋 工件名称: {artifact_name}")
    
    # 显示工件ID
    artifact_id = artifact_event.artifact.artifactId if hasattr(artifact_event.artifact, 'artifactId') else "未知"
    print(f"🆔 工件ID: {artifact_id}")
    
    # 显示工件内容
    if hasattr(artifact_event.artifact, 'parts'):
        print("📄 工件内容:")
        for part in artifact_event.artifact.parts:
            if hasattr(part, 'text'):
                print(f"{part.text}")
            elif hasattr(part, 'root') and hasattr(part.root, 'text'):
                print(f"{part.root.text}")
            elif hasattr(part, 'kind') and part.kind == "file":
                print(f"📎 包含文件附件")

async def query_task(client: A2AClient,task_id:str) -> Optional[Task]:
    """查询任务状态
    
    Args:
        task_id: 任务ID
    """
    try:
        task_response = await client.get_task(
            GetTaskRequest(
                id=str(uuid4()),
                params=TaskQueryParams(id=task_id),
            )
        )
        if isinstance(task_response.root, JSONRPCErrorResponse):

            logger.error(f"获取任务失败: {task_response.root.error}")
            print(f"\n❌ 发生错误: {task_response.root.error}")
            return None
        
        elif isinstance(task_response.root, GetTaskSuccessResponse):

            # 显示完整任务信息
            print("\n" + "=" * 60 + "\n获取到完整任务信息:\n" + "=" * 60)

            task_result = task_response.root.result
            display_task(task_result)

            return task_result

    except Exception as e:
        logger.error(f"获取完整任务失败: {e}")
        return None

class PushNotificationReceiver:
    """推送通知接收器"""
    def __init__(self, host: str, port: int):
        """初始化推送通知接收器
        
        Args:
            host: 主机地址
            port: 端口号
        """
        self.host = host
        self.port = port
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(
            target=lambda loop: loop.run_forever(), args=(self.loop,)
        )
        self.thread.daemon = True
        self.thread.start()

    def start(self):
        """启动推送通知接收服务器"""
        try:
            # 在单独线程中启动服务器，因为当前线程将被用户提示阻塞
            asyncio.run_coroutine_threadsafe(
                self.start_server(),
                self.loop,
            )
            logger.info('======= 推送通知监听器已启动 =======')
        except Exception as e:
            logger.error(f'启动推送通知监听器失败: {e}')

    async def start_server(self):
        """启动HTTP服务器接收推送通知"""
        self.app = Starlette()
        self.app.add_route(
            '/notify', self.handle_notification, methods=['POST']
        )
        self.app.add_route(
            '/notify', self.handle_validation_check, methods=['GET']
        )

        config = uvicorn.Config(
            self.app, host=self.host, port=self.port, log_level='critical'
        )
        self.server = uvicorn.Server(config)
        await self.server.serve()

    async def handle_validation_check(self, request: Request):
        """处理验证请求
        
        Args:
            request: HTTP请求
        """
        validation_token = request.query_params.get('validationToken')
        logger.info(f'收到推送通知验证 => {validation_token}')

        if not validation_token:
            return Response(status_code=400)

        return Response(content=validation_token, status_code=200)

    async def handle_notification(self, request: Request):
        """处理推送通知
        
        Args:
            request: HTTP请求
        """
        data = await request.json()
        logger.info(f'收到推送通知 ===========================> {data}')
        return Response(status_code=200)


async def complete_task(
    client: A2AClient,
    use_push_notifications: bool = False,
    notification_host: str = "localhost",
    notification_port: int = 5000,
    task_id: Optional[str] = None,
    context_id: Optional[str] = None,
    use_streaming: bool = True,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """完成一个智能体任务
    
    Args:
        client: A2A客户端
        use_push_notifications: 是否使用推送通知
        notification_host: 推送通知主机
        notification_port: 推送通知端口
        task_id: 任务ID（如果是继续现有任务）
        context_id: 上下文ID（如果是继续现有任务）
        use_streaming: 是否使用流式请求模式
        
    Returns:
        Tuple[继续执行标志, 上下文ID, 任务ID]
    """
    # 获取用户输入
    prompt = click.prompt(
        '\n请输入您想问智能体的问题 (:q 或 quit 退出)'
    )
    if prompt.lower() in [':q', 'quit']:
        return False, None, None

    # 创建消息对象
    local_task_id = str(uuid4()) if not task_id else task_id
    local_context_id = str(uuid4()) if not context_id else context_id

    # 打印任务ID信息
    print("\n" + "=" * 60)
    print(f"🔹 任务ID: {local_task_id}")
    print(f"🔹 上下文ID: {local_context_id}")
    print("=" * 60)

    message = Message(
        role='user',
        parts=[TextPart(text=prompt)],
        messageId=str(uuid4()),
        taskId=local_task_id,
        contextId=local_context_id,
    )

    # 检查是否需要附加文件
    file_path = click.prompt(
        '是否需要附加文件？（输入文件路径，或直接回车跳过）',
        default='',
        show_default=False,
    )
    if file_path and file_path.strip() != '':
        # 读取文件并添加到消息
        try:
            with open(file_path, 'rb') as f:
                file_content = base64.b64encode(f.read()).decode('utf-8')
                file_name = os.path.basename(file_path)

            message.parts.append(
                Part(
                    root=FilePart(
                        file=FileWithBytes(
                            name=file_name, bytes=file_content
                        )
                    )
                )
            )
            logger.info(f'已添加文件: {file_name}')
        except Exception as e:
            logger.error(f'添加文件失败: {e}')

    # 创建消息参数
    payload = MessageSendParams(
        id=str(uuid4()),
        message=message,
        configuration=MessageSendConfiguration(
            acceptedOutputModes=['text'],
        ),
    )

    # 添加推送通知配置
    if use_push_notifications:
        payload.configuration.pushNotificationConfig = PushNotificationConfig(
                url=f'http://{notification_host}:{notification_port}/notify',
                authentication={'schemes': ['bearer']}
            )
        
    # 发送请求并处理响应
    try:
        logger.info('正在发送请求，等待响应...')
        print("\n" + "=" * 60 + "\n智能体思考中...\n" + "=" * 60)
        
        if use_streaming:
            # 流式模式
            response_stream = client.send_message_streaming(
                SendStreamingMessageRequest(
                    id=str(uuid4()),
                    params=payload,
                )
            )
            
            async for result in response_stream:
                if isinstance(result.root, JSONRPCErrorResponse):
                    logger.error(f"错误: {result.root.error}")
                    print(f"\n❌ 发生错误: {result.root.error}")
                    return False, local_context_id, local_task_id
                
                event = result.root.result
                
                # 处理不同类型的事件
                if isinstance(event, Task):

                    # 使用友好函数显示任务信息
                    display_task(event)
                    
                elif isinstance(event, Message):
                    # 处理消息事件
                    
                    display_message(event)
                
                elif isinstance(event, TaskStatusUpdateEvent):
                    
                    display_task_status_update(event)
                    
                elif isinstance(event, TaskArtifactUpdateEvent):
                    
                    display_artifact_update(event)
                    
                else:
                    print("\n" + "=" * 60)
                    print("📡 收到其他事件:")
                    print("=" * 60)
                    
                    try:
                        # 尝试格式化JSON输出，使其更易读
                        content = json.dumps(
                            event.model_dump(mode='json', exclude_none=True), 
                            ensure_ascii=False, 
                            indent=2
                        )
                        print(content)
                    except:
                        # 如果无法格式化，则使用原始输出
                        print(f"事件内容: {event.model_dump_json(exclude_none=True)}")
        else:
            # 非流式模式
            await client.send_message(
                SendMessageRequest(
                    id=str(uuid4()),
                    params=payload,
                )
            )
            
        # 查询完整任务
        task = await query_task(client, local_task_id)
            
        if task and task.status.state == TaskState.input_required:
            print("\n🔄 智能体需要更多输入...")
            return await complete_task(
                client, 
                use_push_notifications,
                notification_host, 
                notification_port,
                local_task_id, 
                local_context_id,
                use_streaming
            )
        else:
            return True, local_context_id, local_task_id
        
    except Exception as e:
        logger.error(f"处理流式响应时发生错误: {e}")
        print(f"\n❌ 发生错误: {str(e)}")
        return True, local_context_id, local_task_id

@click.command()
@click.option('--url', default='http://localhost:10001', help='智能体服务器地址')
@click.option('--push', is_flag=True, default=False, help='是否启用推送通知')
@click.option('--push-host', default='localhost', help='推送通知接收主机')
@click.option('--push-port', default=5099, help='推送通知接收端口')
@click.option('--task-id', default=None, help='要查询的任务ID（如果提供，将直接查询该任务信息）')
@click.option('--no-streaming', is_flag=True, default=False, help='使用非流式请求模式（等待完整响应而不是流式显示）')
async def main(url: str, push: bool, push_host: str, push_port: int, task_id: Optional[str], no_streaming: bool) -> None:
    """通用A2A智能体客户端"""
    print("\n" + "=" * 60)
    print("📱 通用A2A智能体客户端")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=60) as httpx_client:
        try:
            # 初始化Agent Card解析器
            resolver = A2ACardResolver(httpx_client=httpx_client, base_url=url)
            
            # 获取Agent Card
            print("🔍 正在连接智能体...")
            agent_card = await resolver.get_agent_card()
            print("✅ 成功连接智能体")
            print(f"📝 智能体名称: {agent_card.name}")
            print(f"📝 智能体描述: {agent_card.description}")
            
            # 启动推送通知监听器（如果启用）
            if push:
                push_receiver = PushNotificationReceiver(
                    host=push_host,
                    port=push_port
                )
                push_receiver.start()
                print(f"📢 已启动推送通知接收器: http://{push_host}:{push_port}/notify")
            
            # 初始化A2A客户端
            client = A2AClient(agent_card=agent_card, httpx_client=httpx_client)
            
            # 如果提供了task_id参数，直接查询任务信息
            if task_id:
                print(f"\n🔍 正在查询任务ID: {task_id}")
                task = await query_task(client, task_id)
                if task:
                    print("\n✅ 任务查询完成")
                else:
                    print("\n❌ 任务查询失败")
                return
            
            # 交互循环
            continue_loop = True
            context_id = None  # 首次运行时不指定上下文ID
            local_task_id = None     # 首次运行时不指定任务ID
            
            while continue_loop:
                continue_loop, context_id, local_task_id = await complete_task(
                    client, 
                    push, 
                    push_host, 
                    push_port,
                    None, 
                    context_id,
                    use_streaming=not no_streaming
                )
                
        except Exception as e:
            logger.error(f"错误: {e}")
            print(f"\n❌ 发生错误: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())