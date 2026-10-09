<script setup>
import { computed, ref } from 'vue'

const activeView = ref('setup')
const loading = ref(false)
const notice = ref('')
const errorMessage = ref('')

const userId = ref('user_001')
const projectId = ref(Math.floor(Date.now() / 1000))
const projectName = ref('')
const sessionId = ref(createSessionId())
const selectedFile = ref(null)

const replyState = ref(null)
const answerText = ref('')
const historySessions = ref([])
const selectedHistory = ref(null)
const isRecording = ref(false)
const voiceStatus = ref('')

let voiceSocket = null
let audioContext = null
let mediaStream = null
let audioProcessor = null
let voiceFinalText = ''
let voiceBaseText = ''

const currentQuestion = computed(() => replyState.value?.current_question ?? null)
const evaluations = computed(() => replyState.value?.evaluations ?? [])
const latestEvaluation = computed(() => evaluations.value.at(-1) ?? null)
const finalReport = computed(() => replyState.value?.final_report ?? null)
const isCompleted = computed(() => replyState.value?.reply_step === 'report_completed')
const mainQuestionCount = computed(() => {
  const questions = replyState.value?.questions ?? []
  return questions.filter((question) => question.question_type === 'main').length
})

function createSessionId() {
  const now = new Date()
  const date = [now.getFullYear(), now.getMonth() + 1, now.getDate()]
    .map((value) => String(value).padStart(2, '0'))
    .join('')
  return `reply_${date}_${Date.now().toString().slice(-6)}`
}

function resetMessages() {
  notice.value = ''
  errorMessage.value = ''
}

async function request(url, options = {}) {
  const response = await fetch(url, options)
  let data = null
  try {
    data = await response.json()
  } catch {
    data = null
  }
  if (!response.ok) {
    throw new Error(data?.detail || `请求失败（${response.status}）`)
  }
  return data
}

function selectFile(event) {
  selectedFile.value = event.target.files?.[0] ?? null
}

async function uploadAndStart() {
  resetMessages()
  if (!userId.value.trim()) {
    errorMessage.value = '请输入用户编号'
    return
  }
  if (!selectedFile.value) {
    errorMessage.value = '请选择 TXT 或 Markdown 项目文档'
    return
  }

  loading.value = true
  try {
    const formData = new FormData()
    formData.append('project_id', String(projectId.value))
    formData.append('file', selectedFile.value)

    const uploadResult = await request('/api/documents/upload', {
      method: 'POST',
      body: formData,
    })

    notice.value = `文档已处理，共生成 ${uploadResult.chunk_count} 个文本块。正在生成第一道问题…`
    replyState.value = await request('/api/replies/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId.value.trim(),
        session_id: sessionId.value.trim(),
        project_id: Number(projectId.value),
        project_name: projectName.value.trim(),
      }),
    })

    notice.value = '答辩已开始，请回答当前问题。'
    activeView.value = 'defense'
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    loading.value = false
  }
}

function getVoiceSocketUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws/voice`
}

function resampleTo16k(float32Data, inputSampleRate) {
  if (inputSampleRate === 16000) {
    return float32Data
  }

  const ratio = inputSampleRate / 16000
  const outputLength = Math.max(1, Math.round(float32Data.length / ratio))
  const output = new Float32Array(outputLength)

  for (let outputIndex = 0; outputIndex < outputLength; outputIndex += 1) {
    const sourceIndex = outputIndex * ratio
    const leftIndex = Math.floor(sourceIndex)
    const rightIndex = Math.min(leftIndex + 1, float32Data.length - 1)
    const weight = sourceIndex - leftIndex
    output[outputIndex] =
      float32Data[leftIndex] * (1 - weight) + float32Data[rightIndex] * weight
  }

  return output
}

function float32ToPcm16(float32Data) {
  const pcmData = new Int16Array(float32Data.length)
  for (let index = 0; index < float32Data.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, float32Data[index]))
    pcmData[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
  }
  return pcmData
}

function updateVoiceAnswer() {
  const recognized = [voiceBaseText, voiceFinalText].filter(Boolean).join(' ')
  answerText.value = [recognized, voiceStatus.value.startsWith('正在识别：') ? voiceStatus.value.slice(6) : '']
    .filter(Boolean)
    .join(' ')
}

function cleanupVoiceCapture() {
  if (audioProcessor) {
    audioProcessor.disconnect()
    audioProcessor.onaudioprocess = null
    audioProcessor = null
  }
  if (audioContext) {
    audioContext.close()
    audioContext = null
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop())
    mediaStream = null
  }
  isRecording.value = false
}

async function startVoiceAnswer() {
  resetMessages()
  if (isRecording.value) return

  if (!navigator.mediaDevices?.getUserMedia) {
    errorMessage.value = '当前浏览器不支持麦克风访问'
    return
  }

  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    })

    voiceBaseText = answerText.value.trim()
    voiceFinalText = ''
    voiceStatus.value = '正在连接语音识别…'

    voiceSocket = new WebSocket(getVoiceSocketUrl())
    voiceSocket.binaryType = 'arraybuffer'

    await new Promise((resolve, reject) => {
      voiceSocket.onopen = resolve
      voiceSocket.onerror = () => reject(new Error('语音识别连接失败'))
    })

    voiceSocket.onmessage = (event) => {
      const message = JSON.parse(event.data)
      if (message.type === 'ready') {
        voiceStatus.value = '正在录音，请开始回答…'
      } else if (message.type === 'partial') {
        voiceStatus.value = message.text ? `正在识别：${message.text}` : '正在录音，请继续回答…'
        updateVoiceAnswer()
      } else if (message.type === 'final') {
        voiceFinalText = [voiceFinalText, message.text].filter(Boolean).join(' ')
        voiceStatus.value = '正在录音，请继续回答…'
        updateVoiceAnswer()
      } else if (message.type === 'stopped') {
        voiceStatus.value = '语音识别已停止，可以编辑或提交回答。'
        updateVoiceAnswer()
        if (voiceSocket) voiceSocket.close()
      }
    }

    voiceSocket.send(JSON.stringify({ action: 'start' }))

    audioContext = new AudioContext({ sampleRate: 16000 })
    const source = audioContext.createMediaStreamSource(mediaStream)
    audioProcessor = audioContext.createScriptProcessor(4096, 1, 1)
    audioProcessor.onaudioprocess = (event) => {
      if (!voiceSocket || voiceSocket.readyState !== WebSocket.OPEN) return
      const channelData = event.inputBuffer.getChannelData(0)
      const resampled = resampleTo16k(channelData, audioContext.sampleRate)
      const pcmData = float32ToPcm16(resampled)
      voiceSocket.send(pcmData.buffer)
    }

    source.connect(audioProcessor)
    audioProcessor.connect(audioContext.destination)
    isRecording.value = true
  } catch (error) {
    cleanupVoiceCapture()
    if (voiceSocket) voiceSocket.close()
    voiceSocket = null
    errorMessage.value = error.message || '无法启动语音识别'
  }
}

function stopVoiceAnswer() {
  if (!isRecording.value) return
  voiceStatus.value = '正在整理语音内容…'
  if (voiceSocket?.readyState === WebSocket.OPEN) {
    voiceSocket.send(JSON.stringify({ action: 'stop' }))
  }
  cleanupVoiceCapture()
}

async function submitAnswer() {
  resetMessages()
  if (!answerText.value.trim()) {
    errorMessage.value = '请输入回答内容'
    return
  }

  loading.value = true
  try {
    replyState.value = await request(
      `/api/replies/${encodeURIComponent(sessionId.value)}/answer`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId.value.trim(),
          answer: answerText.value.trim(),
        }),
      },
    )
    answerText.value = ''
    notice.value = isCompleted.value
      ? '答辩已完成，最终报告已生成。'
      : '回答已评价，请继续回答下一道问题。'
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  resetMessages()
  if (!userId.value.trim()) {
    errorMessage.value = '请输入用户编号后再查询历史记录'
    return
  }

  loading.value = true
  try {
    const data = await request(
      `/api/replies/history?user_id=${encodeURIComponent(userId.value.trim())}`,
    )
    historySessions.value = data.sessions ?? []
    selectedHistory.value = null
    activeView.value = 'history'
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    loading.value = false
  }
}

async function loadHistoryDetail(session) {
  resetMessages()
  loading.value = true
  try {
    selectedHistory.value = await request(
      `/api/replies/${encodeURIComponent(session.session_id)}?user_id=${encodeURIComponent(userId.value.trim())}`,
    )
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    loading.value = false
  }
}

async function continueHistory(session) {
  resetMessages()
  loading.value = true
  try {
    const state = await request(
      `/api/replies/${encodeURIComponent(session.session_id)}/resume?user_id=${encodeURIComponent(userId.value.trim())}`,
    )

    sessionId.value = session.session_id
    replyState.value = state
    answerText.value = ''
    activeView.value = 'defense'
    notice.value = '已恢复答辩，可以继续回答当前问题。'
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    loading.value = false
  }
}

async function deleteHistory(session) {
  resetMessages()
  if (!window.confirm(`确定删除“${session.project_name || '未命名项目'}”这场答辩记录吗？删除后无法恢复。`)) {
    return
  }

  loading.value = true
  try {
    await request(
      `/api/replies/${encodeURIComponent(session.session_id)}?user_id=${encodeURIComponent(userId.value.trim())}`,
      { method: 'DELETE' },
    )

    historySessions.value = historySessions.value.filter(
      (item) => item.session_id !== session.session_id,
    )

    if (selectedHistory.value?.session?.session_id === session.session_id) {
      selectedHistory.value = null
    }

    notice.value = '答辩历史删除成功。'
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    loading.value = false
  }
}

function startAnotherReply() {
  replyState.value = null
  selectedFile.value = null
  answerText.value = ''
  projectName.value = ''
  projectId.value = Math.floor(Date.now() / 1000)
  sessionId.value = createSessionId()
  resetMessages()
  activeView.value = 'setup'
}

function formatDate(value) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">R</div>
        <div><strong>Reply Agent</strong><span>AI 项目答辩系统</span></div>
      </div>

      <nav class="nav-list">
        <button :class="{ active: activeView === 'setup' }" @click="activeView = 'setup'">
          <span class="nav-icon">＋</span>新建答辩
        </button>
        <button :disabled="!replyState" :class="{ active: activeView === 'defense' }" @click="activeView = 'defense'">
          <span class="nav-icon">◎</span>在线答辩
        </button>
        <button :class="{ active: activeView === 'history' }" @click="loadHistory">
          <span class="nav-icon">◷</span>历史记录
        </button>
      </nav>

      <div class="sidebar-profile">
        <div class="avatar">{{ userId.slice(0, 1).toUpperCase() || 'U' }}</div>
        <div><strong>{{ userId || '未设置用户' }}</strong><span>当前答辩账号</span></div>
      </div>
    </aside>

    <main class="main-content">
      <header class="topbar">
        <div>
          <p class="eyebrow">PROJECT DEFENSE WORKSPACE</p>
          <h1>{{ activeView === 'setup' ? '创建项目答辩' : activeView === 'defense' ? '在线项目答辩' : '历史答辩记录' }}</h1>
        </div>
        <div class="status-pill"><span></span>服务已连接</div>
      </header>

      <div v-if="notice" class="alert success">{{ notice }}</div>
      <div v-if="errorMessage" class="alert error">{{ errorMessage }}</div>

      <section v-if="activeView === 'setup'" class="page-grid setup-grid">
        <div class="panel form-panel">
          <div class="panel-heading">
            <div><p class="step-label">STEP 01</p><h2>项目信息</h2></div>
            <span class="panel-number">01</span>
          </div>
          <div class="form-grid">
            <label><span>用户编号</span><input v-model="userId" placeholder="例如 user_001" /></label>
            <label><span>项目编号</span><input v-model.number="projectId" type="number" min="1" /></label>
            <label class="full-field"><span>项目名称</span><input v-model="projectName" placeholder="可留空，由 AI 从资料中提取" /></label>
            <label class="full-field">
              <span>答辩会话编号</span>
              <div class="input-action">
                <input v-model="sessionId" />
                <button type="button" class="ghost-button" @click="sessionId = createSessionId()">重新生成</button>
              </div>
            </label>
          </div>
        </div>

        <div class="panel upload-panel">
          <div class="panel-heading">
            <div><p class="step-label">STEP 02</p><h2>上传项目资料</h2></div>
            <span class="panel-number">02</span>
          </div>
          <label class="drop-zone">
            <input type="file" accept=".txt,.md,.markdown" @change="selectFile" />
            <div class="upload-icon">⇧</div>
            <strong>{{ selectedFile?.name || '选择 TXT 或 Markdown 文件' }}</strong>
            <span>文件将被切分、向量化并写入 Chroma</span>
            <small>最大 5 MB</small>
          </label>
          <button class="primary-button wide" :disabled="loading" @click="uploadAndStart">
            {{ loading ? '正在处理项目资料…' : '上传并开始答辩' }}
          </button>
        </div>

        <div class="panel process-panel">
          <p class="step-label">WORKFLOW</p><h2>答辩流程</h2>
          <div class="process-list">
            <div><span>1</span><p><strong>资料解析</strong><small>切分文本并写入向量库</small></p></div>
            <div><span>2</span><p><strong>项目画像</strong><small>提取技术、模块和难点</small></p></div>
            <div><span>3</span><p><strong>动态答辩</strong><small>3 道主问题与智能追问</small></p></div>
            <div><span>4</span><p><strong>能力报告</strong><small>评分、优点与改进建议</small></p></div>
          </div>
        </div>
      </section>

      <section v-else-if="activeView === 'defense'" class="defense-layout">
        <div v-if="replyState" class="defense-main">
          <div class="progress-card">
            <div><span>答辩进度</span><strong>{{ mainQuestionCount }} / 3 主问题</strong></div>
            <div class="progress-track"><span :style="{ width: `${Math.min((mainQuestionCount / 3) * 100, 100)}%` }"></span></div>
            <em>{{ isCompleted ? '已完成' : '进行中' }}</em>
          </div>

          <div v-if="!isCompleted" class="question-card">
            <div class="question-meta">
              <span :class="currentQuestion?.question_type">{{ currentQuestion?.question_type === 'followup' ? '智能追问' : '主问题' }}</span>
              <small>#{{ currentQuestion?.question_id }}</small>
            </div>
            <h2>{{ currentQuestion?.question_content }}</h2>
            <label class="answer-box">
              <span>你的回答</span>
              <textarea v-model="answerText" rows="8" placeholder="结合项目实现说明技术思路和关键细节…" @keydown.ctrl.enter.prevent="submitAnswer"></textarea>
              <div class="voice-controls">
                <button v-if="!isRecording" type="button" class="voice-button" :disabled="loading" @click="startVoiceAnswer">🎙 开始语音回答</button>
                <button v-else type="button" class="voice-button recording" @click="stopVoiceAnswer">■ 停止录音</button>
                <small>{{ voiceStatus || '也可以使用键盘输入回答' }}</small>
              </div>
              <small>Ctrl + Enter 快速提交</small>
            </label>
            <button class="primary-button" :disabled="loading" @click="submitAnswer">{{ loading ? 'AI 正在评价…' : '提交回答' }}</button>
          </div>

          <div v-else class="report-card">
            <div class="score-ring"><strong>{{ finalReport?.total_score ?? 0 }}</strong><span>综合得分</span></div>
            <div class="report-summary">
              <p class="step-label">FINAL REPORT</p><h2>答辩能力报告</h2>
              <p>{{ finalReport?.overall_evaluation }}</p>
              <button class="secondary-button" @click="startAnotherReply">开始新的答辩</button>
            </div>
            <div class="report-columns">
              <article><h3>表现优势</h3><ul><li v-for="item in finalReport?.advantages" :key="item">{{ item }}</li></ul></article>
              <article><h3>存在问题</h3><ul><li v-for="item in finalReport?.problems" :key="item">{{ item }}</li></ul></article>
              <article><h3>改进建议</h3><ul><li v-for="item in finalReport?.suggestions" :key="item">{{ item }}</li></ul></article>
            </div>
          </div>
        </div>

        <aside v-if="replyState" class="evaluation-panel">
          <p class="step-label">LIVE REVIEW</p><h2>最近评价</h2>
          <template v-if="latestEvaluation">
            <div class="evaluation-score"><strong>{{ latestEvaluation.score }}</strong><span>/100</span></div>
            <p>{{ latestEvaluation.evaluation_content }}</p>
            <div v-if="latestEvaluation.need_followup" class="followup-hint">
              <strong>追问方向</strong><span>{{ latestEvaluation.followup_direction }}</span>
            </div>
          </template>
          <p v-else class="muted">提交第一道问题的回答后，这里会显示 AI 评价。</p>
        </aside>
      </section>

      <section v-else class="history-layout">
        <div class="panel history-list">
          <div class="panel-heading">
            <div><p class="step-label">ARCHIVE</p><h2>历史答辩</h2></div>
            <button class="ghost-button" :disabled="loading" @click="loadHistory">刷新</button>
          </div>
          <div v-for="session in historySessions" :key="session.session_id" class="history-item" :class="{ selected: selectedHistory?.session?.session_id === session.session_id }" @click="loadHistoryDetail(session)">
            <span class="history-score">{{ session.total_score ?? '—' }}</span>
            <span><strong>{{ session.project_name }}</strong><small>{{ formatDate(session.created_at) }}</small></span>
            <span class="history-actions">
              <em :class="session.status">{{ session.status === 'completed' ? '已完成' : '进行中' }}</em>
              <button v-if="session.status !== 'completed'" type="button" class="history-continue" :disabled="loading" @click.stop="continueHistory(session)">继续</button>
              <button type="button" class="history-delete" :disabled="loading" @click.stop="deleteHistory(session)">删除</button>
            </span>
          </div>
          <p v-if="!historySessions.length" class="empty-state">当前用户暂无答辩记录。</p>
        </div>

        <div class="panel history-detail">
          <template v-if="selectedHistory">
            <div class="detail-header">
              <div><p class="step-label">SESSION DETAIL</p><h2>{{ selectedHistory.session.project_name }}</h2><span>{{ formatDate(selectedHistory.session.created_at) }}</span></div>
              <div class="detail-score"><strong>{{ selectedHistory.session.total_score ?? '—' }}</strong><span>总分</span></div>
            </div>
            <div class="conversation-list">
              <article v-for="record in selectedHistory.records" :key="record.record_id">
                <div class="message ai-message"><span>AI</span><div><small>{{ record.question_type === 'followup' ? '追问' : '主问题' }}</small><p>{{ record.question_content }}</p></div></div>
                <div class="message user-message"><span>你</span><div><p>{{ record.answer_content }}</p></div></div>
                <div class="record-evaluation"><strong>{{ record.score }} 分</strong><p>{{ record.evaluation_content }}</p></div>
              </article>
            </div>
            <div v-if="selectedHistory.session.overall_evaluation" class="history-report"><h3>最终总结</h3><p>{{ selectedHistory.session.overall_evaluation }}</p></div>
          </template>
          <div v-else class="detail-placeholder"><span>↗</span><h2>选择一条答辩记录</h2><p>查看完整问答、逐题评分和最终总结。</p></div>
        </div>
      </section>
    </main>

    <div v-if="loading" class="loading-overlay"><div class="loader"></div></div>
  </div>
</template>
