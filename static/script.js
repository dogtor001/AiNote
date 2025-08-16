// --- 全局变量 ---
let currentConversationId = null;
let conversations = [];
let sidebarVisible = false;

// --- DOM 元素 ---
const conversationsList = document.getElementById('conversationsList');
const chatContainer = document.getElementById('chatContainer');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const modelSelector = document.getElementById('modelSelector');
const currentChatTitle = document.getElementById('currentChatTitle');
const sidebar = document.getElementById('sidebar');
const mainContent = document.querySelector('.main-content');

// --- SVG 图标 ---
const icons = {
  copy: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`,
  regenerate: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 4v6h-6"></path><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>`,
  edit: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>`,
  delete: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>`
};

// --- 初始化 ---
document.addEventListener('DOMContentLoaded', async () => {
  handleResize(); // Set initial height
  await loadConversations();
  if (conversations.length > 0) {
    currentConversationId = conversations[0].id;
  } else {
    await createNewConversation(false);
  }
  if (currentConversationId) {
    await loadCurrentConversation();
  }
  renderConversationsList();
  setupEventListeners();
  checkLayout();
});

// --- 事件监听器 ---
function setupEventListeners() {
  sendButton.onclick = sendMessage;

  const deleteConvBtn = document.getElementById('deleteConversationBtn');
  deleteConvBtn.innerHTML = icons.delete;
  deleteConvBtn.onclick = () => deleteConversation(currentConversationId);

  mainContent.addEventListener('click', () => {
    if (window.innerWidth <= 900 && sidebarVisible) {
      sidebarVisible = false;
      updateSidebarVisibility();
    }
  });

  window.addEventListener('resize', () => {
    handleResize();
    checkLayout();
  });

  messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  currentChatTitle.addEventListener('click', () => {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(currentChatTitle);
    selection.removeAllRanges();
    selection.addRange(range);
  });

  currentChatTitle.addEventListener('blur', async () => {
    const newTitle = currentChatTitle.textContent.trim();
    const current = conversations.find(c => c.id === currentConversationId);
    if (!current || !newTitle || newTitle === current.title) return;

    try {
      const resp = await fetch(`/api/conversations/${currentConversationId}/title`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle })
      });
      if (resp.ok) await loadConversations();
      else {
        alert('标题更新失败');
        currentChatTitle.textContent = current.title;
      }
    } catch (e) {
      alert('更新标题失败: ' + e.message);
      currentChatTitle.textContent = current.title;
    }
  });

  messageInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 200) + 'px';
  });
}

// --- UI & 布局 ---

function handleResize() {
  document.documentElement.style.setProperty('--app-height', `${window.innerHeight}px`);
}

function checkLayout() {
  const isWide = window.innerWidth > 900;
  if (isWide) {
    sidebarVisible = true;
    updateSidebarVisibility();
  }
}

function toggleSidebar() {
  if (window.innerWidth > 900) return;
  sidebarVisible = !sidebarVisible;
  updateSidebarVisibility();
}

function updateSidebarVisibility() {
  sidebar.classList.toggle('show', sidebarVisible);
}

function showToast(message) {
  const toast = document.createElement('div');
  toast.className = 'toast-notification';
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => toast.classList.add('show'), 10);

  setTimeout(() => {
    toast.classList.remove('show');
    toast.addEventListener('transitionend', () => toast.remove());
  }, 2000);
}

function copyToClipboard(text) {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(() => {
      showToast('文本已复制');
    }).catch(() => showToast('复制失败'));
  } else {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'absolute';
    textArea.style.left = '-9999px';
    document.body.appendChild(textArea);
    textArea.select();
    try {
      document.execCommand('copy');
      showToast('文本已复制');
    } catch (err) {
      showToast('复制失败');
    } finally {
      document.body.removeChild(textArea);
    }
  }
}

// --- 数据 & 对话管理 ---

async function loadConversations() {
  try {
    const response = await fetch('/api/conversations');
    conversations = await response.json();
    renderConversationsList();
  } catch (error) {
    console.error('加载对话列表失败:', error);
  }
}

function renderConversationsList() {
  conversationsList.innerHTML = '';
  conversations.forEach(conversation => {
    const item = document.createElement('div');
    item.className = `conversation-item ${conversation.id === currentConversationId ? 'active' : ''}`;
    item.onclick = () => {
      switchConversation(conversation.id);
      if (window.innerWidth <= 900) {
        sidebarVisible = false;
        updateSidebarVisibility();
      }
    };
    item.innerHTML = `
      <div class="conversation-title">${conversation.title}</div>
      <div class="conversation-meta">
        <span>${conversation.message_count} 条消息</span>
      </div>
    `;
    conversationsList.appendChild(item);
  });
}

async function switchConversation(conversationId) {
  if (currentConversationId === conversationId) return;
  currentConversationId = conversationId;
  renderConversationsList();
  await loadCurrentConversation();
}

async function loadCurrentConversation() {
  if (!currentConversationId) {
    chatContainer.innerHTML = '<div class="loading-indicator">没有选择对话</div>';
    return;
  }
  try {
    const response = await fetch(`/api/conversations/${currentConversationId}/messages`);
    const messages = await response.json();
    const conversation = conversations.find(c => c.id === currentConversationId);
    if (conversation) {
      currentChatTitle.textContent = conversation.title;
      renderMessages(messages, conversation.context_start_message_id);
    }
  } catch (error) {
    console.error('加载对话失败:', error);
  }
}

async function createNewConversation(switchToNew = true) {
  try {
    const response = await fetch('/api/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: '' })
    });
    const newConversation = await response.json();
    await loadConversations();
    if (switchToNew) {
      currentConversationId = newConversation.id;
      renderConversationsList();
      await loadCurrentConversation();
      if (window.innerWidth <= 900) {
        sidebarVisible = false;
        updateSidebarVisibility();
      }
    }
    return newConversation;
  } catch (error) {
    console.error('创建对话失败:', error);
  }
}

async function deleteConversation(conversationId) {
  if (!confirm('确定要删除这个对话吗？此操作不可恢复！')) return;
  try {
    const response = await fetch(`/api/conversations/${conversationId}`, { method: 'DELETE' });
    if (response.ok) {
      const deletedIndex = conversations.findIndex(c => c.id === conversationId);
      await loadConversations();
      if (conversationId === currentConversationId) {
        if (conversations.length > 0) {
          const newIndex = Math.max(0, deletedIndex - 1);
          currentConversationId = conversations[newIndex].id;
        } else {
          await createNewConversation();
          return;
        }
        await loadCurrentConversation();
      }
    }
  } catch (error) {
    console.error('删除对话失败:', error);
  }
}

// --- 消息渲染与操作 ---

function renderMessages(messages, contextStartId) {
  const clearWrapper = document.getElementById('clearContextWrapper');
  chatContainer.innerHTML = '';
  chatContainer.appendChild(clearWrapper);

  messages.forEach(message => {
    addMessageToChat(message.role, message.content, message.time, message.id, message.model, currentConversationId);
    if (contextStartId && message.id === contextStartId) {
      const divider = document.createElement('div');
      divider.className = 'context-divider';
      divider.innerHTML = '<div class="divider-line"></div><div class="divider-text">上下文已清除</div>';
      chatContainer.insertBefore(divider, clearWrapper);
    }
  });

  clearWrapper.style.display = messages.length > 0 ? 'block' : 'none';
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function addMessageToChat(role, content, time, messageId, model, conversationId) {
  if (conversationId !== currentConversationId) return;

  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${role}`;
  messageDiv.dataset.messageId = messageId;

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.textContent = role === 'user' ? '你' : 'AI';

  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content';

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  if (role === 'assistant') {
    bubble.innerHTML = DOMPurify.sanitize(marked.parse(content || ''));
  } else {
    bubble.textContent = content;
  }

  const infoDiv = document.createElement('div');
  infoDiv.className = 'message-info';

  if (time) {
    const timeSpan = document.createElement('span');
    timeSpan.className = 'message-time';
    timeSpan.textContent = formatTime(time);
    infoDiv.appendChild(timeSpan);
  }

  const actions = document.createElement('span');
  actions.className = 'message-actions';

  const copyBtn = document.createElement('button');
  copyBtn.className = 'action-button';
  copyBtn.innerHTML = icons.copy;
  copyBtn.onclick = () => copyToClipboard(content);
  actions.appendChild(copyBtn);

  if (role === 'assistant') {
    const regenBtn = document.createElement('button');
    regenBtn.className = 'action-button';
    regenBtn.innerHTML = icons.regenerate;
    regenBtn.onclick = () => regenerateAssistantMessage(messageId, bubble);
    actions.appendChild(regenBtn);
  }
  if (role === 'user') {
    const editBtn = document.createElement('button');
    editBtn.className = 'action-button';
    editBtn.innerHTML = icons.edit;
    editBtn.onclick = () => editUserMessage(messageId, bubble, content);
    actions.appendChild(editBtn);
  }

  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'action-button delete-message';
  deleteBtn.innerHTML = icons.delete;
  deleteBtn.onclick = () => deleteMessage(messageId, messageDiv);

  infoDiv.appendChild(actions);
  infoDiv.appendChild(deleteBtn);
  contentDiv.appendChild(bubble);
  contentDiv.appendChild(infoDiv);
  messageDiv.appendChild(avatar);
  messageDiv.appendChild(contentDiv);

  const clearWrapper = document.getElementById('clearContextWrapper');
  chatContainer.insertBefore(messageDiv, clearWrapper);

  chatContainer.scrollTop = chatContainer.scrollHeight;
}

async function sendMessage() {
  const message = messageInput.value.trim();
  if (!message) return;

  const model = modelSelector.value;
  const conversationIdForRequest = currentConversationId;

  messageInput.value = '';
  messageInput.dispatchEvent(new Event('input'));
  sendButton.disabled = true;
  sendButton.textContent = '发送中...';

  try {
    const response = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: message,
        model: model,
        conversation_id: conversationIdForRequest
      })
    });

    const data = await response.json();
    if (response.ok) {
      addMessageToChat('user', message, new Date().toISOString(), data.user_id, model, conversationIdForRequest);
      addMessageToChat('assistant', data.response, data.time, data.id, data.model, conversationIdForRequest);

      try {
        new Audio('https://cdn.jsdelivr.net/npm/sound-effects/sounds/mp3/ting.mp3').play();
      } catch (e) {
        console.error("无法播放提示音:", e);
      }

      await loadConversations();
    } else {
      addMessageToChat('assistant', data.error || '发送失败，请重试', new Date().toISOString(), -1, model, conversationIdForRequest);
    }
  } catch (error) {
    addMessageToChat('assistant', '网络错误: ' + error.message, new Date().toISOString(), -1, model, conversationIdForRequest);
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = '发送';
    if (window.innerWidth <= 768) {
      messageInput.blur();
    } else {
      messageInput.focus();
    }
  }
}

async function clearContext() {
  try {
    const response = await fetch(`/api/conversations/${currentConversationId}/clear-context`, { method: 'POST' });
    if (response.ok) {
      await loadConversations();
      await loadCurrentConversation();
    } else {
      alert('清除上下文失败');
    }
  } catch (error) {
    alert('清除上下文失败: ' + error.message);
  }
}

async function regenerateAssistantMessage(messageId, bubbleElement) {
  const regenBtn = bubbleElement.closest('.message-content').querySelector('.action-button[title="重新生成"]');
  try {
    if(regenBtn) regenBtn.disabled = true;
    const resp = await fetch(`/api/messages/${messageId}/regenerate`, { method: 'POST' });
    const data = await resp.json();
    if (data.success) {
      bubbleElement.innerHTML = DOMPurify.sanitize(marked.parse(data.response || ''));
      await loadConversations();
    } else {
      alert('重新生成失败：' + (data.error || '未知错误'));
    }
  } catch (e) {
    alert('重新生成失败：' + e.message);
  } finally {
    if(regenBtn) regenBtn.disabled = false;
  }
}

async function editUserMessage(messageId, bubbleElement, originalContent) {
   const editBtn = bubbleElement.closest('.message-content').querySelector('.action-button[title="编辑"]');
   const edited = prompt('编辑你的消息：', originalContent);
   if (edited === null || edited.trim() === originalContent) return;
   const newText = edited.trim();
   if (!newText) { alert('内容不能为空'); return; }

   try {
     if(editBtn) editBtn.disabled = true;
     const resp = await fetch(`/api/messages/${messageId}/edit`, {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify({ content: newText })
     });
     const data = await resp.json();
     if (data.success) {
       bubbleElement.textContent = data.user.content;
       if (data.assistant) {
         await loadCurrentConversation();
       } else {
         await loadConversations();
       }
     } else {
       alert('保存失败：' + (data.error || '未知错误'));
     }
   } catch (e) {
     alert('编辑失败：' + e.message);
   } finally {
     if(editBtn) editBtn.disabled = false;
   }
}

async function deleteMessage(messageId, messageElement) {
  if (!confirm('确定要删除这条消息吗？')) return;
  try {
    const response = await fetch(`/delete_message/${messageId}`, { method: 'POST' });
    if (response.ok) {
      messageElement.remove();
      await loadConversations();
    }
  } catch (error) {
    alert('删除失败: ' + error.message);
  }
}

function formatTime(timestamp) {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  return date.toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}
