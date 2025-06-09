# A2A Demo - 智能体通信演示

这是一个基于 A2A (Agent-to-Agent) 协议的智能体通信演示项目，展示了如何使用 A2A 协议进行智能体之间的交互。

## 功能特性

- 🤖 支持 A2A 协议的智能体客户端
- 📡 流式响应处理
- 🔔 推送通知支持
- 📝 友好的中文界面
- 📁 文件附件支持
- 🔄 任务状态查询

## 主要组件

### 客户端 (client.py)
通用 A2A 智能体客户端，提供以下功能：
- 连接智能体服务器
- 发送消息和文件
- 接收流式响应
- 处理推送通知
- 查询任务状态

### 智能体 (agent.py)
基于 LangGraph 的智能体实现，具备：
- 搜索能力
- 文件处理
- 对话记忆
- 工具调用

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

或使用 uv：

```bash
uv sync
```

### 2. 配置环境变量

复制 `.env.example` 到 `.env` 并配置必要的参数：

```bash
cp .env.example .env
```

### 3. 启动智能体服务器

```bash
python -m a2a_demo.app.agent
```

### 4. 使用客户端连接

```bash
python -m a2a_demo.app.client --url http://localhost:10001
```

## 使用方法

### 基本对话
启动客户端后，您可以：
1. 输入问题与智能体对话
2. 附加文件（可选）
3. 查看流式响应
4. 输入 `:q` 或 `quit` 退出

### 推送通知
启用推送通知功能：

```bash
python -m a2a_demo.app.client --url http://localhost:10001 --push
```

### 查询特定任务
查询已有任务的状态：

```bash
python -m a2a_demo.app.client --task-id <任务ID>
```

### 非流式模式
使用非流式请求模式：

```bash
python -m a2a_demo.app.client --url http://localhost:10001 --no-streaming
```

## 项目结构

```
a2a_demo/
├── app/
│   ├── agent.py          # 智能体实现
│   ├── client.py         # 客户端实现
│   └── agent_executor.py # 智能体执行器
├── pyproject.toml        # 项目配置
├── .env.example          # 环境变量示例
└── README.md            # 项目说明
```

## 依赖要求

- Python 3.9+
- a2a-python
- langchain-openai
- langgraph
- httpx
- uvicorn
- python-dotenv
- click

## 许可证

MIT License

## 贡献

欢迎提交 Issues 和 Pull Requests！

## 联系方式

如有问题，请通过 Issues 联系。
