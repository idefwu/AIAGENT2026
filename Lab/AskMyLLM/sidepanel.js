// =========================
// 初始化
// =========================

document.addEventListener('DOMContentLoaded', () => {

  chrome.storage.local.get(
    ['apiUrl', 'apiKey', 'model', 'sysPrompt', 'usrPrompt'],
    (result) => {

      if (result.apiUrl)
        document.getElementById('apiUrl').value = result.apiUrl;

      if (result.apiKey)
        document.getElementById('apiKey').value = result.apiKey;

      if (result.model)
        document.getElementById('model').value = result.model;

      if (result.usrPrompt)
        document.getElementById('usrPrompt').value = result.usrPrompt;

      if (result.sysPrompt)
        document.getElementById('sysPrompt').value = result.sysPrompt;
    }
  );
});


// =========================
// 儲存設定
// =========================

document.getElementById('saveConfig').addEventListener('click', () => {

  const config = {
    apiUrl: document.getElementById('apiUrl').value,
    apiKey: document.getElementById('apiKey').value,
    model: document.getElementById('model').value,
    usrPrompt: document.getElementById('usrPrompt').value,
    sysPrompt: document.getElementById('sysPrompt').value
  };

  chrome.storage.local.set(config, () => {
    alert('設定已儲存！');
  });
});


// =========================
// UI 工具
// =========================

function setButtonsDisabled(disabled) {

  document.getElementById('sendBtn').disabled = disabled;
  document.getElementById('exeBtn').disabled = disabled;
  document.getElementById('summarizeBtn').disabled = disabled;

  // clearBtn 不鎖
}

function showLoading() {

  const chat = document.getElementById('chat');

  const div = document.createElement('div');

  div.id = 'loadingMessage';

  div.className = 'msg';

  div.innerHTML = `
    <div class="msg-ai">🤖 AI Assistant</div>

    <div class="loading-wrap">
      <span>正在思考中</span>

      <div class="loading-dots">
        <span></span>
        <span></span>
        <span></span>
      </div>
    </div>
  `;

  chat.appendChild(div);

  chat.scrollTop = chat.scrollHeight;
}

function hideLoading() {

  const loading = document.getElementById('loadingMessage');

  if (loading) {
    loading.remove();
  }
}


function addMessage(role, text) {

  const chat = document.getElementById('chat');

  const div = document.createElement('div');

  div.className = 'msg';

  const isAI = role === "AI";

  const isError = role === "Error";

  let label = "👤 User";
  let labelClass = "msg-user";

  if (isAI) {
    label = "🤖 AI Assistant";
    labelClass = "msg-ai";
  }

  if (isError) {
    label = "⚠️ Error";
    labelClass = "msg-ai";
  }

  let content;

  if (isAI || isError) {

    if (typeof marked !== 'undefined') {

      content = (typeof marked.parse === 'function')
        ? marked.parse(text)
        : marked(text);

    } else {

      content = text.replace(/\n/g, '<br>');

      console.error("Marked library not loaded");
    }

  } else {

    content = text;
  }

  div.innerHTML = `
    <div class="${labelClass}">
      ${label}
    </div>

    <div class="${isAI ? 'msg-ai' : ''}">
      ${content}
    </div>
  `;

  chat.appendChild(div);

  chat.scrollTop = chat.scrollHeight;
}


// =========================
// API 共用函式
// =========================

async function askLLM(userContent, systemPrompt) {

  const settings = await chrome.storage.local.get([
    'apiUrl',
    'apiKey',
    'model'
  ]);

  const fullUrl =
    `${settings.apiUrl.replace(/\/$/, '')}/api/chat/completions`;

  const response = await fetch(fullUrl, {

    method: 'POST',

    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${settings.apiKey}`
    },

    body: JSON.stringify({
      model: settings.model,

      messages: [
        {
          role: "system",
          content: systemPrompt
        },
        {
          role: "user",
          content: userContent
        }
      ]
    })
  });

  const data = await response.json();

  console.log("API Response:", data);

  if (data.choices &&
      data.choices[0] &&
      data.choices[0].message) {

    return data.choices[0].message.content;
  }

  if (data.error) {
    throw new Error(
      data.error.message || JSON.stringify(data.error)
    );
  }

  throw new Error("API 回傳格式不正確");
}


// =========================
// 擷取頁面內容
// =========================

async function getPageContent() {

  const tabs = await chrome.tabs.query({
    active: true,
    currentWindow: true
  });

  const tab = tabs[0];

  if (!tab ||
      !tab.url ||
      tab.url.startsWith('chrome') ||
      tab.url.startsWith('about')) {

    throw new Error("無法存取此頁面內容");
  }

  const injection = await chrome.scripting.executeScript({

    target: { tabId: tab.id },

    func: () => document.body.innerText
  });

  if (!injection || !injection[0]) {
    throw new Error("無法擷取網頁內容");
  }

  return injection[0].result;
}


// =========================
// 發送問題
// =========================

document.getElementById('sendBtn')
.addEventListener('click', async () => {

  const userInput =
    document.getElementById('userInput').value;

  if (!userInput.trim()) return;

  addMessage("User", userInput);

  document.getElementById('userInput').value = '';

  setButtonsDisabled(true);

  showLoading();

  try {

    const settings =
      await chrome.storage.local.get([
        'sysPrompt'
      ]);

    const pageContent = await getPageContent();

    const answer = await askLLM(

      `Context:\n${pageContent.substring(0, 5000)}

Question:
${userInput}`,

      settings.sysPrompt ||
      "You are a helpful assistant."
    );

    hideLoading();

    addMessage("AI", answer);

  } catch (error) {

    hideLoading();

    addMessage(
      "Error",
      "連線失敗: " + error.message
    );

  } finally {

    setButtonsDisabled(false);

    document.getElementById('userInput').focus();
  }
});


// =========================
// 抓重點
// =========================

document.getElementById('summarizeBtn')
.addEventListener('click', async () => {

  setButtonsDisabled(true);

  showLoading();

  addMessage("User", "請幫我抓出這網頁的重點。");

  try {

    const settings =
      await chrome.storage.local.get([
        'sysPrompt'
      ]);

    const pageContent = await getPageContent();

    const summaryTask =
`請針對這篇網頁內容抓出五個重點。
如果內容不足五個重點，
請以專業評論員角色進行分析。
請使用繁體中文。`;

    const answer = await askLLM(

      `網頁內容：
${pageContent.substring(0, 8000)}

任務：
${summaryTask}`,

      settings.sysPrompt ||
      "你是一位資訊分析專家"
    );

    hideLoading();

    addMessage("AI", answer);

  } catch (error) {

    hideLoading();

    addMessage(
      "Error",
      "連線失敗: " + error.message
    );

  } finally {

    setButtonsDisabled(false);
  }
});


// =========================
// 私任務
// =========================

document.getElementById('exeBtn')
.addEventListener('click', async () => {

  setButtonsDisabled(true);

  showLoading();

  try {

    const settings =
      await chrome.storage.local.get([
        'sysPrompt',
        'usrPrompt'
      ]);

    addMessage(
      "User",
      "請執行我自訂義的功能：" +
      settings.usrPrompt
    );

    const pageContent = await getPageContent();

    const answer = await askLLM(

      `網頁內容：
${pageContent.substring(0, 8000)}

任務：
${settings.usrPrompt}`,

      settings.sysPrompt ||
      "你是一位專家助手"
    );

    hideLoading();

    addMessage("AI", answer);

  } catch (error) {

    hideLoading();

    addMessage(
      "Error",
      "連線失敗: " + error.message
    );

  } finally {

    setButtonsDisabled(false);
  }
});


// =========================
// 清除對話
// =========================

document.getElementById('clearBtn')
.addEventListener('click', () => {

  if (confirm("確定要清除對話紀錄嗎？")) {

    document.getElementById('chat').innerHTML = `
      <div style="
        color:#888;
        font-size:13px;
        text-align:center;
      ">
        對話已清除
      </div>
    `;
  }
});


// =========================
// Enter / Ctrl+Enter
// =========================

document.getElementById('userInput')
.addEventListener('keydown', (event) => {

  if (event.key === 'Enter') {

    if (event.ctrlKey || event.shiftKey || event.metaKey) {

      const start = event.target.selectionStart;
      const end = event.target.selectionEnd;
      const value = event.target.value;

      event.target.value =
        value.substring(0, start) +
        "\n" +
        value.substring(end);

      event.target.selectionStart =
      event.target.selectionEnd =
        start + 1;

      event.preventDefault();

    } else {

      event.preventDefault();

      document.getElementById('sendBtn').click();
    }
  }
});
