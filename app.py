import os
import json
import sqlite3
import urllib.request
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# 硅基流动 API 配置
SILICON_API_KEY = 'sk-eeliptsdkjphaujddwpsxoiiyxcehklkdchbvnciemiiuxlb'  # 直接写死
SILICON_API_BASE = 'https://api.siliconflow.cn/v1'

# 可用模型列表
AVAILABLE_MODELS = [
    {"id": "moonshotai/Kimi-K2-Instruct", "name": "Kimi K2"},
    {"id": "deepseek-ai/DeepSeek-R1", "name": "DeepSeek R1"},
    {"id": "zai-org/GLM-4.5", "name": "GLM 4.5"},
    {"id": "Qwen/Qwen3-235B-A22B-Instruct-2507", "name": "Qwen 3.5"},
]

# 数据库路径
DB_PATH = '/app/data/chat.db'
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def generate_default_title():
    """生成类似 20250813-01 的默认标题，保证当日顺序递增且不重复"""
    date_str = datetime.now().strftime('%Y%m%d')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 统计当日已存在的个数，作为下一个序号
    c.execute("SELECT COUNT(*) FROM conversations WHERE title LIKE ?", (f"{date_str}-%",))
    count = c.fetchone()[0] or 0
    # 循环确保唯一
    while True:
        count += 1
        candidate = f"{date_str}-{count:02d}"
        c.execute("SELECT 1 FROM conversations WHERE title = ? LIMIT 1", (candidate,))
        if not c.fetchone():
            conn.close()
            return candidate

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 创建对话表
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT DEFAULT '新对话',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            context_start_message_id INTEGER DEFAULT NULL
        )
    ''')
    
    # 创建消息表
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            model TEXT DEFAULT 'moonshotai/Kimi-K2-Instruct',
            FOREIGN KEY (conversation_id) REFERENCES conversations (id)
        )
    ''')
    
    # 检查是否需要添加 context_start_message_id 字段（数据库迁移）
    try:
        c.execute("SELECT context_start_message_id FROM conversations LIMIT 1")
    except sqlite3.OperationalError:
        # 字段不存在，需要添加
        print("正在迁移数据库，添加 context_start_message_id 字段...")
        c.execute("ALTER TABLE conversations ADD COLUMN context_start_message_id INTEGER DEFAULT NULL")
    
    # 创建默认对话
    c.execute('SELECT COUNT(*) FROM conversations')
    if c.fetchone()[0] == 0:
        default_title = generate_default_title()
        c.execute('INSERT INTO conversations (title) VALUES (?)', (default_title,))
    
    conn.commit()
    conn.close()

init_db()

# 辅助函数

def update_conversation_updated_at(conversation_id: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conversation_id,))
    conn.commit()
    conn.close()

def get_message_by_id(message_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, conversation_id, role, content, timestamp, model FROM messages WHERE id = ?", (message_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "conversation_id": row[1],
        "role": row[2],
        "content": row[3],
        "timestamp": row[4],
        "model": row[5],
    }

def update_message_content(message_id: int, new_content: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE messages 
        SET content = ?, timestamp = CURRENT_TIMESTAMP 
        WHERE id = ?
    """, (new_content, message_id))
    conn.commit()
    conn.close()

def get_conversation_messages(conversation_id):
    """获取指定对话的消息"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, role, content, timestamp, model 
        FROM messages 
        WHERE conversation_id = ? 
        ORDER BY id ASC
    """, (conversation_id,))
    rows = c.fetchall()
    conn.close()
    
    return [{"id": id, "role": role, "content": content, "time": timestamp, "model": model} 
            for id, role, content, timestamp, model in rows]

def get_conversation_messages_with_context(conversation_id):
    """获取指定对话的消息，但只包含上下文起始点之后的消息"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 获取对话的上下文起始点
    c.execute("SELECT context_start_message_id FROM conversations WHERE id = ?", (conversation_id,))
    result = c.fetchone()
    context_start_id = result[0] if result else None
    
    if context_start_id:
        # 只获取上下文起始点之后的消息（不包含起始点本身）
        c.execute("""
            SELECT id, role, content, timestamp, model 
            FROM messages 
            WHERE conversation_id = ? AND id > ?
            ORDER BY id ASC
        """, (conversation_id, context_start_id))
    else:
        # 如果没有设置上下文起始点，获取所有消息
        c.execute("""
            SELECT id, role, content, timestamp, model 
            FROM messages 
            WHERE conversation_id = ? 
            ORDER BY id ASC
        """, (conversation_id,))
    
    rows = c.fetchall()
    conn.close()
    
    return [{"id": id, "role": role, "content": content, "time": timestamp, "model": model} 
            for id, role, content, timestamp, model in rows]

def get_conversation_messages_until(conversation_id: int, max_message_id_inclusive: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT role, content 
        FROM messages 
        WHERE conversation_id = ? AND id <= ?
        ORDER BY id ASC
    """, (conversation_id, max_message_id_inclusive))
    rows = c.fetchall()
    conn.close()
    return [{"role": r, "content": c} for r, c in rows]

def find_last_user_message_before(conversation_id: int, message_id_inclusive: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id 
        FROM messages 
        WHERE conversation_id = ? AND role = 'user' AND id <= ?
        ORDER BY id DESC LIMIT 1
    """, (conversation_id, message_id_inclusive))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def find_next_assistant_message(conversation_id: int, user_message_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id 
        FROM messages 
        WHERE conversation_id = ? AND role = 'assistant' AND id > ?
        ORDER BY id ASC LIMIT 1
    """, (conversation_id, user_message_id))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def create_conversation(title="新对话"):
    """创建新对话"""
    if not title or not title.strip() or title.strip() == '新对话':
        title = generate_default_title()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO conversations (title) VALUES (?)", (title,))
    conversation_id = c.lastrowid
    conn.commit()
    conn.close()
    return conversation_id

def get_conversations():
    """获取所有对话列表"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT c.id, c.title, c.created_at, c.updated_at,
               COUNT(m.id) as message_count,
               c.context_start_message_id
        FROM conversations c
        LEFT JOIN messages m ON c.id = m.conversation_id
        GROUP BY c.id
        ORDER BY c.updated_at DESC
    """)
    rows = c.fetchall()
    conn.close()
    
    conversations = []
    for row in rows:
        conversations.append({
            "id": row[0],
            "title": row[1],
            "created_at": row[2],
            "updated_at": row[3],
            "message_count": row[4],
            "context_start_message_id": row[5]
        })
    return conversations

def save_message(conversation_id, role, content, model="moonshotai/Kimi-K2-Instruct"):
    """保存消息到数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 保存消息
    c.execute("""
        INSERT INTO messages (conversation_id, role, content, model) 
        VALUES (?, ?, ?, ?)
    """, (conversation_id, role, content, model))
    
    # 更新对话的更新时间
    c.execute("""
        UPDATE conversations 
        SET updated_at = CURRENT_TIMESTAMP 
        WHERE id = ?
    """, (conversation_id,))
    
    conn.commit()
    message_id = c.lastrowid
    conn.close()
    return message_id

def delete_message(message_id):
    """删除指定消息"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()
    return True

def delete_conversation(conversation_id):
    """删除指定对话及其所有消息"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    c.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    conn.close()
    return True

def query_ai_api(message, conversation_id, model="moonshotai/Kimi-K2-Instruct"):
    """查询AI API"""
    if not SILICON_API_KEY:
        return "错误：未设置 SILICON_API_KEY"

    try:
        url = f"{SILICON_API_BASE}/chat/completions"
        headers = {
            'Authorization': f'Bearer {SILICON_API_KEY}',
            'Content-Type': 'application/json',
        }
        
        # 获取当前对话的历史记录（只包含上下文起始点之后的消息）
        history = get_conversation_messages_with_context(conversation_id)
        messages = [{"role": msg["role"], "content": msg["content"]} for msg in history]
        
        payload = {
            'model': model,
            'messages': messages,
        }

        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
        with urllib.request.urlopen(req) as response:
            resp_data = json.loads(response.read().decode())

        try:
            return resp_data['choices'][0]['message']['content']
        except:
            return json.dumps(resp_data, ensure_ascii=False)
    except Exception as e:
        print(f"AI API 调用失败: {e}")
        return f"AI 服务暂时不可用，请稍后重试。错误信息: {str(e)}"

def query_ai_api_with_messages(messages, model="moonshotai/Kimi-K2-Instruct"):
    """使用自定义消息历史调用 AI 接口"""
    if not SILICON_API_KEY:
        return "错误：未设置 SILICON_API_KEY"
    
    try:
        url = f"{SILICON_API_BASE}/chat/completions"
        headers = {
            'Authorization': f'Bearer {SILICON_API_KEY}',
            'Content-Type': 'application/json',
        }
        payload = {
            'model': model,
            'messages': messages,
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
        with urllib.request.urlopen(req) as resp:
            resp_data = json.loads(resp.read().decode())
        try:
            return resp_data['choices'][0]['message']['content']
        except:
            return json.dumps(resp_data, ensure_ascii=False)
    except Exception as e:
        print(f"AI API 调用失败: {e}")
        return f"AI 服务暂时不可用，请稍后重试。错误信息: {str(e)}"

def clear_conversation_context(conversation_id):
    """清除对话的上下文记忆，设置新的上下文起始点"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 获取对话中最后一条消息的ID作为新的上下文起始点
    c.execute("""
        SELECT MAX(id) FROM messages WHERE conversation_id = ?
    """, (conversation_id,))
    result = c.fetchone()
    
    if result and result[0]:
        # 设置新的上下文起始点为最后一条消息的ID
        c.execute("""
            UPDATE conversations 
            SET context_start_message_id = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (result[0], conversation_id))
        conn.commit()
        conn.close()
        return True
    else:
        conn.close()
        return False

@app.route("/", methods=["GET"])
def index():
    return render_template('index.html')

@app.route("/api/conversations", methods=["GET"])
def api_conversations():
    """获取所有对话列表"""
    return jsonify(get_conversations())

@app.route("/api/conversations", methods=["POST"]) 
def api_create_conversation():
    """创建新对话"""
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    conversation_id = create_conversation(title)
    return jsonify({"id": conversation_id, "title": title or ""})

@app.route("/api/conversations/<int:conversation_id>", methods=["DELETE"]) 
def api_delete_conversation(conversation_id):
    """删除对话"""
    success = delete_conversation(conversation_id)
    return jsonify({"success": success})

@app.route("/api/conversations/<int:conversation_id>/title", methods=["PATCH", "POST"]) 
def api_update_conversation_title(conversation_id):
    """更新对话标题"""
    data = request.get_json() or {}
    new_title = (data.get("title") or "").strip()
    if not new_title:
        return jsonify({"success": False, "error": "标题不能为空"}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_title, conversation_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "title": new_title})

@app.route("/api/conversations/<int:conversation_id>/messages", methods=["GET"]) 
def api_get_messages(conversation_id):
    """获取指定对话的消息"""
    messages = get_conversation_messages(conversation_id)
    return jsonify(messages)

@app.route("/chat", methods=["POST"]) 
def chat():
    """处理聊天请求"""
    data = request.get_json()
    message = data.get("message", "")
    model = data.get("model", "moonshotai/Kimi-K2-Instruct")
    conversation_id = data.get("conversation_id", 1)  # 默认使用第一个对话
    
    # 保存用户消息
    user_id = save_message(conversation_id, "user", message, model)
    
    # 获取AI回复
    reply = query_ai_api(message, conversation_id, model)
    
    # 保存AI回复
    assistant_id = save_message(conversation_id, "assistant", reply, model)
    
    response_data = {
        "response": reply,
        "id": assistant_id,
        "user_id": user_id,
        "time": datetime.now(timezone.utc).isoformat(),
        "model": model
    }
    
    return jsonify(response_data)

@app.route("/api/models", methods=["GET"]) 
def api_models():
    """获取可用模型列表"""
    return jsonify(AVAILABLE_MODELS)

@app.route("/delete_message/<int:message_id>", methods=["POST"]) 
def delete_message_route(message_id):
    """删除指定消息"""
    success = delete_message(message_id)
    return jsonify({"success": success})

@app.route("/api/messages/<int:message_id>/regenerate", methods=["POST"]) 
def regenerate_assistant_message(message_id):
    """重新生成指定助手消息的内容，基于其之前的最近一次用户消息及其历史"""
    msg = get_message_by_id(message_id)
    if not msg:
        return jsonify({"success": False, "error": "消息不存在"}), 404
    if msg["role"] != "assistant":
        return jsonify({"success": False, "error": "只能对助手消息重新生成"}), 400
    conversation_id = msg["conversation_id"]
    model = msg["model"] or "moonshotai/Kimi-K2-Instruct"
    # 找到对应的最近一次用户消息
    last_user_id = find_last_user_message_before(conversation_id, message_id)
    if not last_user_id:
        return jsonify({"success": False, "error": "找不到对应的用户消息"}), 400
    # 历史取到该用户消息（包含）
    history_messages = get_conversation_messages_until(conversation_id, last_user_id)
    # 用该历史生成新的助手回复
    new_reply = query_ai_api_with_messages(history_messages, model)
    # 更新该助手消息
    update_message_content(message_id, new_reply)
    update_conversation_updated_at(conversation_id)
    return jsonify({
        "success": True,
        "id": message_id,
        "response": new_reply,
        "time": datetime.now(timezone.utc).isoformat(),
        "model": model,
    })

@app.route("/api/messages/<int:message_id>/edit", methods=["POST"]) 
def edit_user_message(message_id):
    """编辑用户消息，并基于新的内容重新生成紧随其后的助手回复"""
    msg = get_message_by_id(message_id)
    if not msg:
        return jsonify({"success": False, "error": "消息不存在"}), 404
    if msg["role"] != "user":
        return jsonify({"success": False, "error": "只能编辑用户消息"}), 400
    data = request.get_json() or {}
    new_content = (data.get("content") or "").strip()
    if not new_content:
        return jsonify({"success": False, "error": "内容不能为空"}), 400
    conversation_id = msg["conversation_id"]
    model = msg["model"] or "moonshotai/Kimi-K2-Instruct"
    # 更新该用户消息内容
    update_message_content(message_id, new_content)
    # 查找紧随其后的助手消息
    assistant_id = find_next_assistant_message(conversation_id, message_id)
    assistant_payload = None
    if (assistant_id is not None):
        # 历史取到该用户消息（包含）
        history_messages = get_conversation_messages_until(conversation_id, message_id)
        # 基于更新后的消息生成新的助手内容
        new_reply = query_ai_api_with_messages(history_messages, model)
        update_message_content(assistant_id, new_reply)
        assistant_payload = {
            "id": assistant_id,
            "response": new_reply,
            "time": datetime.now(timezone.utc).isoformat(),
            "model": model,
        }
    update_conversation_updated_at(conversation_id)
    return jsonify({
        "success": True,
        "user": {
            "id": message_id,
            "content": new_content,
            "time": datetime.now(timezone.utc).isoformat(),
        },
        "assistant": assistant_payload
    })

@app.route("/api/conversations/<int:conversation_id>/clear_context", methods=["POST"]) 
def api_clear_conversation_context(conversation_id):
    """清除对话的上下文记忆"""
    success = clear_conversation_context(conversation_id)
    return jsonify({"success": success})

# 提供连字符路径的兼容路由
@app.route("/api/conversations/<int:conversation_id>/clear-context", methods=["POST"]) 
def api_clear_conversation_context_dash(conversation_id):
    success = clear_conversation_context(conversation_id)
    return jsonify({"success": success})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
