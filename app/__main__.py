"""
搜索智能体服务器入口
"""
import logging
import os
import sys
import pathlib

# 添加父目录到Python路径，使app模块可以被正确导入
current_dir = pathlib.Path(__file__).parent.absolute()
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import click
import httpx
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryPushNotifier, InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from dotenv import load_dotenv

# 使用绝对导入
from app.agent import SearchAgent
from app.agent_executor import SearchAgentExecutor


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """API密钥缺失异常"""

@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=10001)
@click.option('--model', 'model', default='gpt-4o-mini', help='OpenAI模型名称')
def main(host, port, model):
    """启动搜索智能体服务器"""
    try:
        if not os.getenv('OPENAI_API_KEY'):
            raise MissingAPIKeyError('OPENAI_API_KEY环境变量未设置')
        
        if not os.getenv('TAVILY_API_KEY'):
            raise MissingAPIKeyError('TAVILY_API_KEY环境变量未设置')

        capabilities = AgentCapabilities(streaming=True, pushNotifications=True)
        skill = AgentSkill(
            id='search_web',
            name='网络搜索工具',
            description='帮助搜索互联网以获取最新信息',
            tags=['搜索', '信息检索', '事实查询'],
            examples=['谁是目前的美国总统?', '最新的AI技术突破是什么?'],
        )
        agent_card = AgentCard(
            name='搜索智能体',
            description='使用Tavily API搜索互联网回答问题的智能体',
            url=f'http://{host}:{port}/',
            version='1.0.0',
            defaultInputModes=SearchAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=SearchAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )

        httpx_client = httpx.AsyncClient()
        request_handler = DefaultRequestHandler(
            agent_executor=SearchAgentExecutor(model_name=model),
            task_store=InMemoryTaskStore(),
            push_notifier=InMemoryPushNotifier(httpx_client),
        )
        server = A2AStarletteApplication(
            agent_card=agent_card, http_handler=request_handler
        )

        logger.info(f"启动搜索智能体服务器，使用模型：{model}")
        logger.info(f"服务地址: http://{host}:{port}/")
        logger.info(f"Agent Card: http://{host}:{port}/.well-known/agent.json")
        uvicorn.run(server.build(), host=host, port=port)

    except MissingAPIKeyError as e:
        logger.error(f'错误: {e}')
        sys.exit(1)
    except Exception as e:
        logger.error(f'服务器启动时发生错误: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
