/**
 * 301 Downloader Frontend Controller
 */

// Application State
const state = {
    currentUrl: "",
    analyzedData: null,
    formatType: "video", // "video" | "audio"
    selectedQuality: "best",
    activeJobId: null,
    eventSource: null,
    lastDownloadedUrl: null,
    lastDownloadedType: null,
    lastDownloadedTitle: null
};

// DOM Elements
const urlInput = document.getElementById("urlInput");
const clearBtn = document.getElementById("clearBtn");
const pasteBtn = document.getElementById("pasteBtn");
const analyzeBtn = document.getElementById("analyzeBtn");
const analyzeBtnIcon = document.getElementById("analyzeBtnIcon");
const analyzeBtnText = document.getElementById("analyzeBtnText");
const errorBox = document.getElementById("errorBox");
const errorMessage = document.getElementById("errorMessage");

const loadingSkeleton = document.getElementById("loadingSkeleton");
const resultCard = document.getElementById("resultCard");

const videoThumb = document.getElementById("videoThumb");
const videoDuration = document.getElementById("videoDuration");
const platformBadge = document.getElementById("platformBadge");
const platformIcon = document.getElementById("platformIcon");
const platformName = document.getElementById("platformName");
const videoUploader = document.getElementById("videoUploader");
const videoTitle = document.getElementById("videoTitle");

const tabVideo = document.getElementById("tabVideo");
const tabAudio = document.getElementById("tabAudio");
const videoOptionsPanel = document.getElementById("videoOptionsPanel");
const audioOptionsPanel = document.getElementById("audioOptionsPanel");
const videoOptionsGrid = document.getElementById("videoOptionsGrid");
const audioOptionsGrid = document.getElementById("audioOptionsGrid");
const selectedSummary = document.getElementById("selectedSummary");
const startDownloadBtn = document.getElementById("startDownloadBtn");

const progressCard = document.getElementById("progressCard");
const progressSpinner = document.getElementById("progressSpinner");
const progressStage = document.getElementById("progressStage");
const progressSpeed = document.getElementById("progressSpeed");
const progressEta = document.getElementById("progressEta");
const progressPercent = document.getElementById("progressPercent");
const progressBar = document.getElementById("progressBar");
const completeActions = document.getElementById("completeActions");
const downloadFileLink = document.getElementById("downloadFileLink");
const previewBtn = document.getElementById("previewBtn");
const openFolderActionBtn = document.getElementById("openFolderActionBtn");

const openFolderBtn = document.getElementById("openFolderBtn");
const toggleHistoryBtn = document.getElementById("toggleHistoryBtn");
const historyBadge = document.getElementById("historyBadge");
const historyDrawer = document.getElementById("historyDrawer");
const historyList = document.getElementById("historyList");

const installAppBtn = document.getElementById("installAppBtn");
const sharePublicBtn = document.getElementById("sharePublicBtn");
const shareModal = document.getElementById("shareModal");
const publicStatusBadge = document.getElementById("publicStatusBadge");
const publicInactiveBox = document.getElementById("publicInactiveBox");
const publicActiveBox = document.getElementById("publicActiveBox");
const publicUrlDisplay = document.getElementById("publicUrlDisplay");
const publicQrImg = document.getElementById("publicQrImg");
const localUrlDisplay = document.getElementById("localUrlDisplay");
const activateTunnelBtn = document.getElementById("activateTunnelBtn");
const activateTunnelBtnText = document.getElementById("activateTunnelBtnText");

const playerModal = document.getElementById("playerModal");
const playerModalTitle = document.getElementById("playerModalTitle");
const inlineVideo = document.getElementById("inlineVideo");
const inlineAudio = document.getElementById("inlineAudio");

let deferredPrompt = null;

// Register PWA Service Worker
if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.js").catch((err) => {
            console.log("ServiceWorker registration failed:", err);
        });
    });
}

// PWA Install Prompt Handler
window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    if (installAppBtn) installAppBtn.classList.remove("hidden");
});

window.addEventListener("appinstalled", () => {
    if (installAppBtn) installAppBtn.classList.add("hidden");
    deferredPrompt = null;
});


// --- Event Listeners Initialization ---
document.addEventListener("DOMContentLoaded", () => {
    urlInput.addEventListener("input", onUrlInput);
    urlInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") analyzeUrl();
    });

    clearBtn.addEventListener("click", () => {
        urlInput.value = "";
        onUrlInput();
        urlInput.focus();
    });

    pasteBtn.addEventListener("click", async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (text) {
                urlInput.value = text.trim();
                onUrlInput();
                analyzeUrl();
            }
        } catch (err) {
            console.warn("Clipboard read error:", err);
            urlInput.focus();
        }
    });

    analyzeBtn.addEventListener("click", analyzeUrl);

    tabVideo.addEventListener("click", () => switchFormatType("video"));
    tabAudio.addEventListener("click", () => switchFormatType("audio"));

    startDownloadBtn.addEventListener("click", startDownload);

    openFolderBtn.addEventListener("click", openWindowsFolder);
    openFolderActionBtn.addEventListener("click", openWindowsFolder);
    toggleHistoryBtn.addEventListener("click", () => toggleHistory(true));

    if (sharePublicBtn) {
        sharePublicBtn.addEventListener("click", openShareModal);
    }

    if (installAppBtn) {
        installAppBtn.addEventListener("click", async () => {
            if (deferredPrompt) {
                deferredPrompt.prompt();
                const { outcome } = await deferredPrompt.userChoice;
                if (outcome === "accepted") {
                    installAppBtn.classList.add("hidden");
                }
                deferredPrompt = null;
            }
        });
    }

    previewBtn.addEventListener("click", openPlayer);

    // Initial check on history files
    loadHistory();
});


function onUrlInput() {
    const val = urlInput.value.trim();
    if (val.length > 0) {
        clearBtn.classList.remove("hidden");
    } else {
        clearBtn.classList.add("hidden");
    }
}


function showError(msg) {
    errorMessage.textContent = msg;
    errorBox.classList.remove("hidden");
}

function hideError() {
    errorBox.classList.add("hidden");
}


// --- Analyze URL ---
async function analyzeUrl() {
    const url = urlInput.value.trim();
    if (!url) {
        showError("Татах видеоны линкийг оруулна уу.");
        urlInput.focus();
        return;
    }

    hideError();
    resultCard.classList.add("hidden");
    progressCard.classList.add("hidden");
    loadingSkeleton.classList.remove("hidden");

    // UI Loading state
    analyzeBtn.disabled = true;
    analyzeBtnIcon.className = "fa-solid fa-spinner animate-spin";
    analyzeBtnText.textContent = "Шинжилж байна...";

    try {
        const res = await fetch("/api/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url })
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Шинжилгээ хийхэд алдаа гарлаа");
        }

        state.analyzedData = data;
        state.currentUrl = url;
        renderVideoDetails(data);
        renderOptions(data);

        loadingSkeleton.classList.add("hidden");
        resultCard.classList.remove("hidden");

        // Scroll smoothly to result
        resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });

    } catch (err) {
        loadingSkeleton.classList.add("hidden");
        showError(err.message || "Сервертэй холбогдоход алдаа гарлаа.");
    } finally {
        analyzeBtn.disabled = false;
        analyzeBtnIcon.className = "fa-solid fa-magnifying-glass";
        analyzeBtnText.textContent = "Шинжлэх";
    }
}


function renderVideoDetails(data) {
    videoThumb.src = data.thumbnail || "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400";
    videoDuration.textContent = data.duration_str || "--:--";
    videoTitle.textContent = data.title;
    videoUploader.textContent = data.uploader;

    // Platform Badge
    const p = data.platform || { name: "Web Video", color: "text-indigo-400", bg: "bg-indigo-500/10", border: "border-indigo-500/30" };
    platformBadge.className = `px-2.5 py-0.5 rounded-full text-xs font-semibold flex items-center space-x-1.5 ${p.bg} ${p.border} ${p.color} border`;
    platformName.textContent = p.name;

    // FontAwesome icon class
    const iconMap = {
        youtube: "fa-brands fa-youtube",
        facebook: "fa-brands fa-facebook",
        instagram: "fa-brands fa-instagram",
        tiktok: "fa-brands fa-tiktok",
        "x-twitter": "fa-brands fa-x-twitter",
        globe: "fa-solid fa-globe"
    };
    platformIcon.className = iconMap[p.icon] || "fa-solid fa-video";
}


function renderOptions(data) {
    // Populate Video Options
    videoOptionsGrid.innerHTML = "";
    const videoOptions = data.video_options || [];

    videoOptions.forEach((opt, idx) => {
        const card = document.createElement("div");
        const isDefault = opt.id === "best" || idx === 0;
        card.className = `option-card cursor-pointer p-3 rounded-xl border border-slate-800 bg-slate-950/60 flex flex-col justify-between space-y-1.5 ${isDefault ? "selected" : ""}`;
        card.dataset.id = opt.id;
        card.dataset.label = opt.label;

        card.innerHTML = `
            <div class="flex items-center justify-between">
                <span class="font-bold text-sm text-white">${opt.resolution}</span>
                <span class="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${opt.badge === '4K' || opt.badge === 'HD' ? 'bg-indigo-500/20 text-indigo-300' : 'bg-slate-800 text-slate-400'}">${opt.badge}</span>
            </div>
            <div class="text-xs text-slate-400 truncate">${opt.label}</div>
            <div class="text-[11px] text-slate-500 flex items-center justify-between pt-1 border-t border-slate-900">
                <span>Хэмжээ:</span>
                <span class="text-slate-300 font-medium">${opt.filesize_str}</span>
            </div>
        `;

        card.addEventListener("click", () => {
            videoOptionsGrid.querySelectorAll(".option-card").forEach(c => c.classList.remove("selected"));
            card.classList.add("selected");
            state.selectedQuality = opt.id;
            updateSummary();
        });

        videoOptionsGrid.appendChild(card);
    });

    // Populate Audio Options
    audioOptionsGrid.innerHTML = "";
    const audioOptions = data.audio_options || [];

    audioOptions.forEach((opt) => {
        const card = document.createElement("div");
        const isDefault = opt.id === "192" || opt.is_recommended;
        card.className = `option-card cursor-pointer p-3 rounded-xl border border-slate-800 bg-slate-950/60 flex flex-col justify-between space-y-1.5 ${isDefault ? "selected" : ""}`;
        card.dataset.id = opt.id;
        card.dataset.label = opt.label;

        card.innerHTML = `
            <div class="flex items-center justify-between">
                <span class="font-bold text-sm text-white">${opt.id} kbps MP3</span>
                <span class="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${opt.is_recommended ? 'bg-pink-500/20 text-pink-300 border border-pink-500/30' : 'bg-slate-800 text-slate-400'}">${opt.badge}</span>
            </div>
            <div class="text-xs text-slate-400 truncate">${opt.label}</div>
            <div class="text-[11px] text-slate-500 flex items-center justify-between pt-1 border-t border-slate-900">
                <span>Хэмжээ:</span>
                <span class="text-slate-300 font-medium">${opt.filesize_str}</span>
            </div>
        `;

        card.addEventListener("click", () => {
            audioOptionsGrid.querySelectorAll(".option-card").forEach(c => c.classList.remove("selected"));
            card.classList.add("selected");
            state.selectedQuality = opt.id;
            updateSummary();
        });

        audioOptionsGrid.appendChild(card);
    });

    // Set defaults
    state.formatType = "video";
    state.selectedQuality = "best";
    switchFormatType("video");
}


function switchFormatType(type) {
    state.formatType = type;
    if (type === "video") {
        tabVideo.className = "flex-1 py-2 rounded-lg text-sm font-semibold transition-all flex items-center justify-center space-x-2 bg-indigo-600 text-white shadow";
        tabAudio.className = "flex-1 py-2 rounded-lg text-sm font-semibold transition-all flex items-center justify-center space-x-2 text-slate-400 hover:text-slate-200";
        videoOptionsPanel.classList.remove("hidden");
        audioOptionsPanel.classList.add("hidden");

        const selected = videoOptionsGrid.querySelector(".option-card.selected") || videoOptionsGrid.querySelector(".option-card");
        if (selected) {
            state.selectedQuality = selected.dataset.id;
        }
    } else {
        tabAudio.className = "flex-1 py-2 rounded-lg text-sm font-semibold transition-all flex items-center justify-center space-x-2 bg-pink-600 text-white shadow";
        tabVideo.className = "flex-1 py-2 rounded-lg text-sm font-semibold transition-all flex items-center justify-center space-x-2 text-slate-400 hover:text-slate-200";
        audioOptionsPanel.classList.remove("hidden");
        videoOptionsPanel.classList.add("hidden");

        const selected = audioOptionsGrid.querySelector(".option-card.selected") || audioOptionsGrid.querySelector(".option-card");
        if (selected) {
            state.selectedQuality = selected.dataset.id;
        }
    }
    updateSummary();
}


function updateSummary() {
    if (state.formatType === "video") {
        const selCard = videoOptionsGrid.querySelector(`[data-id="${state.selectedQuality}"]`);
        const label = selCard ? selCard.dataset.label : "Хамгийн өндөр чанар";
        selectedSummary.textContent = `MP4 Видео - ${label}`;
        selectedSummary.className = "text-indigo-400 font-semibold";
    } else {
        const selCard = audioOptionsGrid.querySelector(`[data-id="${state.selectedQuality}"]`);
        const label = selCard ? selCard.dataset.label : `${state.selectedQuality} kbps`;
        selectedSummary.textContent = `MP3 Аудио - ${label}`;
        selectedSummary.className = "text-pink-400 font-semibold";
    }
}


// --- Start Download Job ---
async function startDownload() {
    if (!state.currentUrl) return;

    hideError();
    progressCard.classList.remove("hidden");
    completeActions.classList.add("hidden");
    progressSpinner.classList.remove("hidden");
    progressBar.style.width = "0%";
    progressPercent.textContent = "0%";
    progressStage.textContent = "Таталтыг эхлүүлж байна...";
    progressSpeed.innerHTML = '<i class="fa-solid fa-gauge-high mr-1 text-indigo-400"></i>Холбогдож байна...';
    progressEta.innerHTML = '<i class="fa-regular fa-hourglass mr-1 text-purple-400"></i>--';

    startDownloadBtn.disabled = true;
    startDownloadBtn.classList.add("opacity-60", "cursor-not-allowed");

    // Scroll to progress card
    progressCard.scrollIntoView({ behavior: "smooth", block: "nearest" });

    try {
        const res = await fetch("/api/download", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                url: state.currentUrl,
                format_type: state.formatType,
                quality: state.selectedQuality
            })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Таталт эхлүүлэхэд алдаа гарлаа");

        state.activeJobId = data.job_id;
        listenProgress(data.job_id);

    } catch (err) {
        showError(err.message);
        startDownloadBtn.disabled = false;
        startDownloadBtn.classList.remove("opacity-60", "cursor-not-allowed");
        progressCard.classList.add("hidden");
    }
}


// --- Real-time Progress Tracking with SSE ---
function listenProgress(jobId) {
    if (state.eventSource) {
        state.eventSource.close();
    }

    const sse = new EventSource(`/api/stream/${jobId}`);
    state.eventSource = sse;

    sse.onmessage = (event) => {
        try {
            const job = JSON.parse(event.data);
            handleJobUpdate(job);
        } catch (e) {
            console.error("Error parsing progress update:", e);
        }
    };

    sse.onerror = () => {
        console.warn("SSE disconnected, falling back to polling");
        sse.close();
        pollProgress(jobId);
    };
}


function pollProgress(jobId) {
    const interval = setInterval(async () => {
        try {
            const res = await fetch(`/api/progress/${jobId}`);
            if (!res.ok) {
                clearInterval(interval);
                return;
            }
            const job = await res.json();
            handleJobUpdate(job);

            if (job.status === "completed" || job.status === "error") {
                clearInterval(interval);
            }
        } catch (e) {
            console.error("Polling error:", e);
        }
    }, 800);
}


function handleJobUpdate(job) {
    if (job.status === "downloading" || job.status === "processing" || job.status === "queued") {
        progressStage.textContent = job.stage || "Боловсруулж байна...";
        const pct = Math.max(0, Math.min(100, job.percent || 0));
        progressBar.style.width = `${pct}%`;
        progressPercent.textContent = `${pct}%`;

        if (job.speed && job.speed !== "--") {
            progressSpeed.innerHTML = `<i class="fa-solid fa-gauge-high mr-1 text-indigo-400"></i>${job.speed}`;
        }
        if (job.eta && job.eta !== "--") {
            progressEta.innerHTML = `<i class="fa-regular fa-hourglass mr-1 text-purple-400"></i>Үлдсэн: ${job.eta}`;
        }
    } else if (job.status === "completed") {
        if (state.eventSource) state.eventSource.close();

        progressBar.style.width = "100%";
        progressPercent.textContent = "100%";
        progressStage.textContent = "Амжилттай татагдлаа! (" + (job.filesize_str || "") + ")";
        progressSpinner.classList.add("hidden");

        // Action links
        downloadFileLink.href = job.download_url;
        downloadFileLink.setAttribute("download", job.public_name || "download");

        state.lastDownloadedUrl = job.download_url;
        state.lastDownloadedType = job.format_type;
        state.lastDownloadedTitle = job.public_name;

        completeActions.classList.remove("hidden");
        startDownloadBtn.disabled = false;
        startDownloadBtn.classList.remove("opacity-60", "cursor-not-allowed");

        // Trigger auto browser download
        setTimeout(() => {
            const triggerLink = document.createElement("a");
            triggerLink.href = job.download_url;
            triggerLink.setAttribute("download", job.public_name || "download");
            document.body.appendChild(triggerLink);
            triggerLink.click();
            document.body.removeChild(triggerLink);
        }, 300);

        // Refresh History
        loadHistory();

    } else if (job.status === "error") {
        if (state.eventSource) state.eventSource.close();
        progressSpinner.classList.add("hidden");
        progressStage.textContent = "Таталт амжилтгүй боллоо";
        showError(job.error_message || "Файл татахад алдаа гарлаа");

        startDownloadBtn.disabled = false;
        startDownloadBtn.classList.remove("opacity-60", "cursor-not-allowed");
    }
}


// --- In-Browser Media Player ---
function openPlayer() {
    if (!state.lastDownloadedUrl) return;

    playerModalTitle.textContent = state.lastDownloadedTitle || "Тоглуулагч";

    if (state.lastDownloadedType === "video" || state.lastDownloadedTitle.endsWith(".mp4")) {
        inlineAudio.pause();
        inlineAudio.classList.add("hidden");
        inlineVideo.classList.remove("hidden");
        inlineVideo.src = state.lastDownloadedUrl;
        inlineVideo.play();
    } else {
        inlineVideo.pause();
        inlineVideo.classList.add("hidden");
        inlineAudio.classList.remove("hidden");
        inlineAudio.src = state.lastDownloadedUrl;
        inlineAudio.play();
    }

    playerModal.classList.remove("hidden");
}

function closePlayer() {
    inlineVideo.pause();
    inlineAudio.pause();
    inlineVideo.src = "";
    inlineAudio.src = "";
    playerModal.classList.add("hidden");
}


// --- History Management ---
async function loadHistory() {
    try {
        const res = await fetch("/api/history");
        const files = await res.json();
        renderHistory(files);
    } catch (e) {
        console.warn("Could not load history:", e);
    }
}

function renderHistory(files) {
    if (!files || files.length === 0) {
        historyBadge.classList.add("hidden");
        historyList.innerHTML = `
            <div class="text-center py-12 text-slate-500">
                <i class="fa-regular fa-folder-open text-3xl mb-2 opacity-50"></i>
                <p class="text-xs">Одоогоор татаж авсан файл байхгүй байна.</p>
            </div>
        `;
        return;
    }

    historyBadge.textContent = files.length;
    historyBadge.classList.remove("hidden");

    historyList.innerHTML = "";
    files.forEach((file) => {
        const isMp3 = file.ext === "MP3";
        const item = document.createElement("div");
        item.className = "p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 hover:border-slate-700 transition-all flex items-center justify-between gap-3";

        item.innerHTML = `
            <div class="flex items-center space-x-3 min-w-0 flex-1">
                <div class="w-9 h-9 rounded-lg ${isMp3 ? 'bg-pink-500/10 text-pink-400' : 'bg-indigo-500/10 text-indigo-400'} flex items-center justify-center flex-shrink-0 text-sm font-bold">
                    ${isMp3 ? '<i class="fa-solid fa-music"></i>' : '<i class="fa-solid fa-film"></i>'}
                </div>
                <div class="min-w-0 flex-1">
                    <div class="text-xs font-semibold text-slate-200 truncate" title="${file.display_name}">${file.display_name}</div>
                    <div class="text-[10px] text-slate-500 flex items-center space-x-2 mt-0.5">
                        <span class="font-medium text-slate-400">${file.filesize_str}</span>
                        <span>•</span>
                        <span class="uppercase">${file.ext}</span>
                    </div>
                </div>
            </div>
            <div class="flex items-center space-x-1.5 flex-shrink-0">
                <a href="${file.download_url}" download="${file.display_name}" title="Татах" class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors text-xs">
                    <i class="fa-solid fa-download"></i>
                </a>
                <button onclick="deleteFile('${file.filename}')" title="Устгах" class="p-1.5 rounded-lg bg-slate-800/60 hover:bg-red-500/20 text-slate-500 hover:text-red-400 transition-colors text-xs">
                    <i class="fa-regular fa-trash-can"></i>
                </button>
            </div>
        `;

        historyList.appendChild(item);
    });
}

async function deleteFile(filename) {
    if (!confirm("Энэ файлыг устгах уу?")) return;
    try {
        const res = await fetch(`/api/file/${encodeURIComponent(filename)}`, { method: "DELETE" });
        if (res.ok) {
            loadHistory();
        }
    } catch (e) {
        console.error(e);
    }
}

function toggleHistory(open) {
    if (open) {
        historyDrawer.classList.remove("translate-x-full");
        loadHistory();
    } else {
        historyDrawer.classList.add("translate-x-full");
    }
}


// --- Windows Explorer Open Folder ---
async function openWindowsFolder() {
    try {
        await fetch("/api/open-folder", { method: "POST" });
    } catch (e) {
        console.error("Open folder error:", e);
    }
}


// --- Share & Public Internet Modal ---
async function openShareModal() {
    try {
        const res = await fetch("/api/network-info");
        const data = await res.json();
        renderShareData(data);
        shareModal.classList.remove("hidden");
    } catch (e) {
        console.error("Error getting network info:", e);
    }
}

function renderShareData(data) {
    if (localUrlDisplay) localUrlDisplay.value = data.network_url || "";

    if (data.public_url) {
        publicStatusBadge.textContent = "Идэвхтэй байна";
        publicStatusBadge.className = "text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
        publicInactiveBox.classList.add("hidden");
        publicActiveBox.classList.remove("hidden");
        publicUrlDisplay.value = data.public_url;
        publicQrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(data.public_url)}`;
    } else {
        publicStatusBadge.textContent = "Унтраалттай";
        publicStatusBadge.className = "text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-400";
        publicInactiveBox.classList.remove("hidden");
        publicActiveBox.classList.add("hidden");
    }
}

async function activatePublicTunnel() {
    activateTunnelBtn.disabled = true;
    activateTunnelBtn.classList.add("opacity-70", "cursor-wait");
    activateTunnelBtnText.textContent = "Линк үүсгэж байна... (Түр хүлээнэ үү)";

    try {
        const res = await fetch("/api/enable-public-tunnel", { method: "POST" });
        const data = await res.json();
        if (res.ok && data.public_url) {
            renderShareData({ public_url: data.public_url, network_url: localUrlDisplay.value });
        } else {
            alert(data.detail || "Нийтийн линк асаахад алдаа гарлаа");
        }
    } catch (e) {
        alert("Сервертэй холбогдоход алдаа гарлаа: " + e.message);
    } finally {
        activateTunnelBtn.disabled = false;
        activateTunnelBtn.classList.remove("opacity-70", "cursor-wait");
        activateTunnelBtnText.textContent = "Нийтийн линк үүсгэх (Cloudflare Tunnel)";
    }
}

function closeShareModal() {
    shareModal.classList.add("hidden");
}

function copyPublicUrl() {
    if (publicUrlDisplay.value) {
        navigator.clipboard.writeText(publicUrlDisplay.value);
        alert("Нийтийн линк амжилттай хуулагдлаа!\n\n" + publicUrlDisplay.value + "\n\nЭнэ линкийг найз нөхөддөө чатаар явуулж болно.");
    }
}

function copyLocalUrl() {
    if (localUrlDisplay.value) {
        navigator.clipboard.writeText(localUrlDisplay.value);
        alert("Wi-Fi хаяг хуулагдлаа: " + localUrlDisplay.value);
    }
}

