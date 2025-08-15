# Ai Note - 简洁的本地 AI 对话应用

Ai Note 是一个轻量级的、自托管的 Web 应用程序，旨在提供一个简单、高效的界面，用于与大型语言模型（LLM）进行交互。所有的对话数据都存储在本地的 SQLite 数据库中，确保了数据的私密性和持久性。

## ✨ 功能特性

- **持久化存储**：所有对话都保存在本地 SQLite 数据库中，方便回顾和管理。
- **多对话管理**：可以创建、命名、切换和删除多个独立的对话。
- **上下文控制**：可以随时“清除上下文”，让 AI 忘记之前的对话内容，开始新的话题，同时保留历史记录。
- **消息编辑与重新生成**：可以编辑自己发送过的消息，或让 AI 重新生成它的回答。
- **模型选择**：支持在运行时切换不同的 AI 模型（通过 SiliconFlow API）。
- **响应式界面**：界面适配桌面和移动设备。
- **简单部署**：基于 Python Flask 和原生 JavaScript，无需复杂的前端框架或构建过程。

## ⚙️ 技术栈

- **后端**: Python, Flask
- **前端**: HTML, CSS, JavaScript (原生)
- **数据库**: SQLite

## 🚀 快速开始

### 1. 环境要求

- Python 3.x
- Flask

### 2. 安装

首先，克隆或下载本仓库到您的本地计算机。

然后，安装所需的 Python 包（主要是 Flask）：

```bash
pip install Flask
```

### 3. 配置 API 密钥

在开始运行之前，您需要一个来自 [SiliconFlow](https://siliconflow.cn/) 的 API 密钥。

打开 `app.py` 文件，找到以下这行：

```python
# 硅基流动 API 配置
SILICON_API_KEY = 'sk-eeliptsdkjphaujddwpsxoiiyxcehklkdchbvnciemiiuxlb'  # 直接写死
```

请将 `'sk-...'` 这个字符串替换为您自己的真实 API 密钥。

### 4. 运行应用

在项目根目录下，运行以下命令启动应用：

```bash
python app.py
```

应用启动后，您会看到类似以下的输出：

```
 * Running on http://0.0.0.0:5000
```

现在，打开您的浏览器，访问 `http://localhost:5000` 或 `http://<您的服务器IP>:5000` 即可开始使用。

## 📁 文件结构

```
.
├── app.py              # Flask 后端主程序 (API, 数据库逻辑)
├── templates/
│   └── index.html      # 应用的全部前端代码 (HTML, CSS, JavaScript)
└── data/
    └── chat.db         # (应用首次运行时自动创建) SQLite 数据库文件
```

---
由 Jules (AI 软件工程师) 创建。
