"""
搜索智能体执行器 - 处理A2A请求并执行智能体
"""
import logging
import sys
import pathlib

# 添加父目录到Python路径，使app模块可以被正确导入
current_dir = pathlib.Path(__file__).parent.absolute()
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    InternalError,
    InvalidParamsError,
    Part,
    Task,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import (
    new_agent_text_message,
    new_task,
)
from a2a.utils.errors import ServerError

from app.agent import SearchAgent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SearchAgentExecutor(AgentExecutor):
    """搜索智能体执行器"""

    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.agent = SearchAgent(model_name=model_name)

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        
        print("***************")
        print(f"context: {context.__dict__}")

        """执行智能体"""
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError("请求参数无效"))

        query = context.get_user_input()
        task = context.current_task

        print(f"处理查询: {query}")
        print(f"当前任务: {task}")

        if not task:
            task = new_task(context.message)
            event_queue.enqueue_event(task)
        
        updater = TaskUpdater(event_queue, task.id, task.contextId)
        
        try:
            response = self.agent.stream(query, task.id)
            async for item in response:
                
                status = item["status"]
                content = item["content"]

                if status != "completed":
                    print(f"更新状态: {status}, 内容: {content}")
                    updater.update_status(
                        status,
                        new_agent_text_message(
                            content,
                            task.contextId,
                            task.id,
                        ),
                    )
                else:
                    print(f"任务已经完成: {content}")
                    updater.add_artifact(
                        [Part(root=TextPart(text=content))],
                        name="search_result",
                    )
                    updater.complete(
                        new_agent_text_message(
                            '任务完成',
                            task.contextId,
                            task.id,)
                    )
                    break

        except Exception as e:
            logger.error(f"处理响应流时发生错误: {e}")
            raise ServerError(error=InternalError()) from e

    def _validate_request(self, context: RequestContext) -> bool:
        """验证请求"""
        # 简单实现，返回False表示请求有效
        return False

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        """取消任务"""
        raise ServerError(error=UnsupportedOperationError("不支持取消任务"))
