let socket;
let mediaRecorder;
let mediaStream;
let audioContext;
let analyserNode;
let micSourceNode;
let vadRafId;
let recognition;
let isRunning = false;
let isSpeaking = false;
let isPausedForPlayback = false;
let speechDetected = false;
let silenceStartedAt = 0;
let speechStartedAt = 0;
let recordedChunks = [];

// Keep a more forgiving end-of-utterance window so Whisper gets the full command.
const SILENCE_THRESHOLD_DB = -53;
const SILENCE_DURATION_MS = 2400;
const MIN_SPEECH_DB = -45;
const MIN_ACTIVE_SPEECH_MS = 1500;
const isBackendOrigin = window.location.port === "8000";
const HTTP_BASE = isBackendOrigin ? window.location.origin : "http://127.0.0.1:8000";
const WS_BASE = HTTP_BASE.replace(/^http/, "ws");

const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const apiKeyInput = document.getElementById("apiKeyInput");
const saveApiKeyBtn = document.getElementById("saveApiKeyBtn");
const statusEl = document.getElementById("status");
const routeEl = document.getElementById("route");
const actionEl = document.getElementById("action");
const audioStateEl = document.getElementById("audioState");
const userText = document.getElementById("userText");
const aiText = document.getElementById("aiText");
const resultView = document.getElementById("resultView");
const planView = document.getElementById("planView");
const audioPlayer = document.getElementById("audioPlayer");
const textForm = document.getElementById("textForm");
const textInput = document.getElementById("textInput");

audioPlayer.addEventListener("ended", () => {
    if (isRunning) {
        resumeRecordingAfterPlayback();
    }
});

audioPlayer.addEventListener("error", () => {
    if (isRunning) {
        resumeRecordingAfterPlayback();
    }
});

function setStatus(value) {
    statusEl.textContent = value;
}

function setAudioState(value) {
    audioStateEl.textContent = value;
}

function setClarificationState(message) {
    setStatus("Need info");
    setAudioState("Clarification needed");
    aiText.textContent = message;
}

function getApiKey() {
    return localStorage.getItem("financeVoiceApiKey") || "";
}

function setApiKey(value) {
    const clean = value.trim();
    if (clean) {
        localStorage.setItem("financeVoiceApiKey", clean);
    } else {
        localStorage.removeItem("financeVoiceApiKey");
    }
    apiKeyInput.value = clean;
}

function resetButtons(running) {
    startBtn.disabled = running;
    stopBtn.disabled = !running;
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatMoney(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
        return "-";
    }
    return number.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

function renderPlan(plan = []) {
    if (!Array.isArray(plan) || !plan.length) {
        planView.innerHTML = "<li>No plan available.</li>";
        return;
    }

    planView.innerHTML = plan.map((step) => `<li>${escapeHtml(step)}</li>`).join("");
}

function stopVadLoop() {
    if (vadRafId) {
        cancelAnimationFrame(vadRafId);
        vadRafId = undefined;
    }
}

function closeAudioContext() {
    if (audioContext) {
        audioContext.close().catch(() => {});
        audioContext = undefined;
    }
    analyserNode = undefined;
    micSourceNode = undefined;
}

function startVadLoop() {
    stopVadLoop();

    const tick = () => {
        if (!isRunning || isPausedForPlayback || !analyserNode || !mediaRecorder || mediaRecorder.state !== "recording") {
            vadRafId = window.requestAnimationFrame(tick);
            return;
        }

        const buffer = new Float32Array(analyserNode.fftSize);
        analyserNode.getFloatTimeDomainData(buffer);

        let sumSquares = 0;
        for (const sample of buffer) {
            sumSquares += sample * sample;
        }
        const rms = Math.sqrt(sumSquares / buffer.length);
        const levelDb = 20 * Math.log10(rms || 0.00001);
        const now = Date.now();

        if (levelDb > MIN_SPEECH_DB) {
            if (!speechDetected) {
                speechStartedAt = now;
            }
            speechDetected = true;
            silenceStartedAt = 0;
            setAudioState("Listening");
        } else if (speechDetected && levelDb < SILENCE_THRESHOLD_DB) {
            if (!silenceStartedAt) {
                silenceStartedAt = now;
            } else if (now - silenceStartedAt >= SILENCE_DURATION_MS && now - speechStartedAt >= MIN_ACTIVE_SPEECH_MS) {
                speechDetected = false;
                silenceStartedAt = 0;
                speechStartedAt = 0;
                stopCurrentRecording();
                vadRafId = window.requestAnimationFrame(tick);
                return;
            }
        } else {
            silenceStartedAt = 0;
        }

        vadRafId = window.requestAnimationFrame(tick);
    };

    vadRafId = window.requestAnimationFrame(tick);
}

function pauseRecordingForPlayback() {
    isPausedForPlayback = true;
    isSpeaking = true;
    setAudioState("Playing response");
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.requestData();
        mediaRecorder.stop();
    }
    stopVadLoop();
}

function resumeRecordingAfterPlayback() {
    if (!isRunning || !socket || socket.readyState !== WebSocket.OPEN) {
        return;
    }

    isPausedForPlayback = false;
    isSpeaking = false;
    if (!mediaStream) {
        return;
    }

    if (!mediaRecorder || mediaRecorder.state !== "recording") {
        createRecorder();
        mediaRecorder.start();
        startVadLoop();
    }
    setAudioState("Recording");
    setStatus("Listening");
}

function renderResults(action, data) {
    if (!data || (Array.isArray(data) && data.length === 0)) {
        resultView.textContent = "No records found.";
        return;
    }

    if (action === "get_invoices" && Array.isArray(data)) {
        resultView.innerHTML = invoiceTable(data);
        return;
    }

    if (action === "invoice_summary" && data.items) {
        resultView.innerHTML = `
            <div class="metric-grid">
                <div><span>Total</span><strong>${formatMoney(data.total_amount)}</strong></div>
                <div><span>Pending</span><strong>${formatMoney(data.pending_amount)}</strong></div>
                <div><span>Paid</span><strong>${formatMoney(data.paid_amount)}</strong></div>
                <div><span>Count</span><strong>${escapeHtml(data.count)}</strong></div>
            </div>
            ${invoiceTable(data.items)}
        `;
        return;
    }

    if (action === "get_transactions" && Array.isArray(data)) {
        resultView.innerHTML = transactionTable(data);
        return;
    }

    if (action === "summarize_transactions" && data.items) {
        resultView.innerHTML = `
            <div class="metric-grid">
                <div><span>Income</span><strong>${formatMoney(data.income_total)}</strong></div>
                <div><span>Expenses</span><strong>${formatMoney(data.expense_total)}</strong></div>
                <div><span>Net</span><strong>${formatMoney(data.net_total)}</strong></div>
                <div><span>Count</span><strong>${escapeHtml(data.transaction_count)}</strong></div>
            </div>
            ${categoryList(data.expense_by_category)}
            ${transactionTable(data.items)}
        `;
        return;
    }

    if (action === "get_reminders" && Array.isArray(data)) {
        resultView.innerHTML = reminderTable(data);
        return;
    }

    if (typeof data === "object") {
        resultView.innerHTML = `
            <dl class="kv-list">
                ${Object.entries(data).map(([key, value]) => `
                    <div>
                        <dt>${escapeHtml(key.replaceAll("_", " "))}</dt>
                        <dd>${escapeHtml(value)}</dd>
                    </div>
                `).join("")}
            </dl>
        `;
        return;
    }

    resultView.textContent = String(data);
}

function invoiceTable(items) {
    return `
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Client</th>
                        <th>Amount</th>
                        <th>Status</th>
                        <th>Due</th>
                    </tr>
                </thead>
                <tbody>
                    ${items.map((invoice) => `
                        <tr>
                            <td>${escapeHtml(invoice.id)}</td>
                            <td>${escapeHtml(invoice.client_name)}</td>
                            <td>${formatMoney(invoice.amount)}</td>
                            <td>${escapeHtml(invoice.status)}</td>
                            <td>${escapeHtml(invoice.due_date || "-")}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        </div>
    `;
}

function transactionTable(items) {
    return `
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Type</th>
                        <th>Amount</th>
                        <th>Category</th>
                        <th>Description</th>
                    </tr>
                </thead>
                <tbody>
                    ${items.map((transaction) => `
                        <tr>
                            <td>${escapeHtml(transaction.id)}</td>
                            <td>${escapeHtml(transaction.type)}</td>
                            <td>${formatMoney(transaction.amount)}</td>
                            <td>${escapeHtml(transaction.category || "-")}</td>
                            <td>${escapeHtml(transaction.description || "-")}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        </div>
    `;
}

function reminderTable(items) {
    return `
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Title</th>
                        <th>Due</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${items.map((reminder) => `
                        <tr>
                            <td>${escapeHtml(reminder.id)}</td>
                            <td>${escapeHtml(reminder.title)}</td>
                            <td>${escapeHtml(reminder.due_at || "-")}</td>
                            <td>${escapeHtml(reminder.status)}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        </div>
    `;
}

function categoryList(categories = {}) {
    const entries = Object.entries(categories);
    if (!entries.length) {
        return "";
    }
    return `
        <div class="category-list">
            ${entries.map(([category, amount]) => `
                <div><span>${escapeHtml(category)}</span><strong>${formatMoney(amount)}</strong></div>
            `).join("")}
        </div>
    `;
}

async function sendChatMessage(message, keepListening = false) {
    const cleanMessage = message.trim();
    if (!cleanMessage) {
        return;
    }

    setStatus("Processing");
    userText.textContent = cleanMessage;

    try {
        const apiKey = getApiKey();
        const response = await fetch(`${HTTP_BASE}/api/chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...(apiKey ? { "X-API-Key": apiKey } : {}),
            },
            body: JSON.stringify({ message: cleanMessage }),
        });
        const text = await response.text();
        const data = text ? JSON.parse(text) : {};
        if (!response.ok) {
            throw new Error(data.detail || `Request failed with ${response.status}`);
        }

        aiText.textContent = data.response || data.detail || "No response";
        routeEl.textContent = data.route || "-";
        actionEl.textContent = data.action || "-";
        renderResults(data.action, data.data);
        renderPlan(data.plan);
        if (data.audio_url) {
            audioPlayer.src = `${HTTP_BASE}${data.audio_url}`;
            audioPlayer.play();
        }
        setStatus(keepListening ? "Listening" : "Ready");
    } catch (error) {
        setStatus("Error");
        aiText.textContent = `Request failed: ${error.message}`;
    }
}

function getSpeechRecognition() {
    return window.SpeechRecognition || window.webkitSpeechRecognition;
}

function startBrowserSpeechRecognition() {
    const SpeechRecognition = getSpeechRecognition();
    recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = true;
    recognition.interimResults = false;

    recognition.addEventListener("result", async (event) => {
        const transcript = Array.from(event.results)
            .slice(event.resultIndex)
            .map((result) => result[0].transcript)
            .join(" ")
            .trim();

        if (transcript) {
            await sendChatMessage(transcript, true);
        }
    });

    recognition.addEventListener("error", (event) => {
        setStatus("Error");
        setAudioState("Browser STT failed");
        aiText.textContent = `Speech recognition failed: ${event.error}`;
    });

    recognition.addEventListener("end", () => {
        if (isRunning && !isSpeaking) {
            recognition.start();
        }
    });

    isRunning = true;
    recognition.start();
    resetButtons(true);
    setStatus("Listening");
    setAudioState("Browser STT");
}

function supportedMimeType() {
    const types = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/ogg;codecs=opus",
    ];
    return types.find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

function createRecorder() {
    const options = supportedMimeType() ? { mimeType: supportedMimeType() } : undefined;
    mediaRecorder = new MediaRecorder(mediaStream, options);
    recordedChunks = [];

    mediaRecorder.addEventListener("dataavailable", (event) => {
        if (event.data.size > 0) {
            recordedChunks.push(event.data);
            setAudioState("Recording");
        }
    });

    mediaRecorder.addEventListener("stop", async () => {
        await sendRecordedAudio();

        if (isRunning && socket && socket.readyState === WebSocket.OPEN && !isPausedForPlayback) {
            createRecorder();
            mediaRecorder.start();
            setStatus("Listening");
            setAudioState("Recording");
        }
    });
}

async function sendRecordedAudio() {
    if (!recordedChunks.length || !socket || socket.readyState !== WebSocket.OPEN) {
        return;
    }

    setStatus("Processing");
    setAudioState("Sending");
    const blob = new Blob(recordedChunks, { type: mediaRecorder.mimeType || "audio/webm" });
    recordedChunks = [];
    socket.send(await blob.arrayBuffer());
    socket.send("flush");
}

function stopSegmentTimer() {
    stopVadLoop();
}

function stopCurrentRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.requestData();
        mediaRecorder.stop();
    }
}

async function startBackendAudioStreaming() {
    setStatus("Connecting");
    setAudioState("Opening mic");

    const apiKey = getApiKey();
    socket = new WebSocket(`${WS_BASE}/ws${apiKey ? `?api_key=${encodeURIComponent(apiKey)}` : ""}`);

    socket.addEventListener("open", async () => {
        mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
            },
        });
        audioContext = new AudioContext();
        micSourceNode = audioContext.createMediaStreamSource(mediaStream);
        analyserNode = audioContext.createAnalyser();
        analyserNode.fftSize = 2048;
        micSourceNode.connect(analyserNode);
        createRecorder();
        isRunning = true;
        mediaRecorder.start();
        speechDetected = false;
        silenceStartedAt = 0;
        speechStartedAt = 0;
        startVadLoop();
        resetButtons(true);
        setStatus("Listening");
        setAudioState("Recording");
    });

    socket.addEventListener("message", (event) => {
        const data = JSON.parse(event.data);
        if (data.error) {
            if (data.error === "clarification_required") {
                userText.textContent = data.input_text || userText.textContent;
                routeEl.textContent = data.route || "-";
                actionEl.textContent = data.action || "-";
                renderPlan(data.plan);
                setClarificationState(data.response_text || data.response || "I need a little more detail.");
                if (data.audio_url) {
                    audioPlayer.src = `${HTTP_BASE}${data.audio_url}`;
                    audioPlayer.play().catch(() => {});
                }
                return;
            }

            setStatus("Error");
            setAudioState(
                data.stage === "stt"
                    ? "Speech to text failed"
                    : data.stage === "tts"
                        ? "Voice output failed"
                        : data.stage === "orchestrator"
                            ? "Command processing failed"
                            : "Voice failed",
            );
            aiText.textContent = data.error;
            userText.textContent = data.input_text || userText.textContent;
            return;
        }

        userText.textContent = data.input_text || "";
        aiText.textContent = data.response_text || "";
        routeEl.textContent = data.route || "-";
        actionEl.textContent = data.action || "-";
        renderResults(data.action, data.data);
        renderPlan(data.plan);
        setStatus(isRunning ? "Listening" : "Stopped");

        if (data.audio_url) {
            audioPlayer.src = `${HTTP_BASE}${data.audio_url}`;
            pauseRecordingForPlayback();
            audioPlayer.play().catch(() => {
                resumeRecordingAfterPlayback();
            });
        } else {
            pauseRecordingForPlayback();
            resumeRecordingAfterPlayback();
        }
    });

    socket.addEventListener("close", () => {
        if (statusEl.textContent !== "Error" && isRunning) {
            setStatus("Disconnected");
        }
        isRunning = false;
        stopSegmentTimer();
        closeAudioContext();
        isPausedForPlayback = false;
        speechDetected = false;
        silenceStartedAt = 0;
        speechStartedAt = 0;
        resetButtons(false);
    });

    socket.addEventListener("error", () => {
        setStatus("Error");
        setAudioState("Socket error");
        aiText.textContent = "Could not connect to the backend WebSocket. Make sure FastAPI is running on port 8000.";
    });
}

startBtn.addEventListener("click", async () => {
    await startBackendAudioStreaming();
});

stopBtn.addEventListener("click", () => {
    isRunning = false;
    isPausedForPlayback = false;
    speechDetected = false;
    silenceStartedAt = 0;
    speechStartedAt = 0;

    if (recognition) {
        recognition.stop();
        recognition = undefined;
    }

    stopSegmentTimer();
    stopCurrentRecording();
    stopVadLoop();
    closeAudioContext();
    audioPlayer.pause();
    audioPlayer.removeAttribute("src");
    audioPlayer.load();

    if (mediaStream) {
        mediaStream.getTracks().forEach((track) => track.stop());
        mediaStream = undefined;
    }

    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close();
    }

    setStatus("Stopped");
    setAudioState("Idle");
    resetButtons(false);
});

textForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await sendChatMessage(textInput.value);
    textInput.value = "";
});

saveApiKeyBtn.addEventListener("click", () => {
    setApiKey(apiKeyInput.value);
    setStatus(apiKeyInput.value.trim() ? "API key saved" : "API key cleared");
});

apiKeyInput.value = getApiKey();
