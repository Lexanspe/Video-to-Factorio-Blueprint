// ==========================================================================
// Factorio 2.0 Video to Blueprint Generator — Interactive Web Controller
// ==========================================================================

// Çoklu Dil Çevirileri (i18n Dictionaries)
const i18n = {
  en: {
    appTitle: "FACTORIO 2.0",
    appSubtitle: "VIDEO & ROM BLUEPRINT GENERATOR",
    secVideoSource: "Video / GIF Source",
    btnSelectVideo: "Select Video",
    btnLoadDemo: "Load Demo",
    demoAnimName: "Built-in Demo Animation",
    activeLabel: "Active:",
    ratioWord: "Ratio",
    framesWord: "Frames",
    
    secCircuitEngine: "Circuit Engine",
    engineV3Desc: "16 frames/signal 2-bit grayscale, single-combinator TrueColor adapter (* 5.5M), Selector clock.",
    engineV2Desc: "3 frames/pack 9-bit color (27-bit packing), compact ROM architecture.",
    engineV1Desc: "1 frame/combinator 24-bit TrueColor RGB, direct signal mapping.",
    engineWarning: "High resolution may produce a very large blueprint size.",
    
    secMonitorResolution: "Monitor Resolution",
    lblHeight: "Height:",
    resSummaryTemplate: "Resolution: {w} x {h} ({lamps} Lamps) • {ratio} Ratio",
    
    secRomPlacement: "ROM Circuit Placement",
    optHorizontal: "Horizontal",
    optVertical: "Vertical",
    dirLeft: "◀ Left",
    dirRight: "Right ▶",
    dirBothHoriz: "◀ Dual / Both ▶",
    dirTop: "▲ Top",
    dirBottom: "Bottom ▼",
    dirBothVert: "▲ Dual / Both ▼",
    
    chkCompactRomTitle: "Compact ROM (Recommended)",
    chkCompactRomDesc: "Removes spacing between combinators (0 tiles).",
    chkFillAllRowsTitle: "Fill All Rows (Recommended)",
    chkFillAllRowsDesc: "Distributes ROM combinators across multiple rows along monitor.",
    
    lblSubstationQuality: "Substation Quality:",
    subQualityLegendary: "Legendary",
    subQualityEpic: "Epic",
    subQualityRare: "Rare",
    subQualityUncommon: "Uncommon",
    subQualityNormal: "Normal (Standard)",
    subQualityNone: "No Substation (External Power / Sandbox)",
    
    secFpsAndFrames: "FPS & Frame Count",
    chkAllVideo: "All Video",
    lblMaxFrames: "Max Frames:",
    
    secRomSlicing: "ROM Slicing (Modular Parts)",
    lblPartCount: "Part Count:",
    partsCountBadge: "{n} Part{s}",
    
    btnGenerateSingle: "GENERATE BLUEPRINT",
    btnGeneratePart: "GENERATE PART {part}/{total}",
    btnAbort: "ABORT",
    btnSaveBlueprint: "Save .txt",
    
    statusReady: "Ready. Press button to generate blueprint.",
    statusAborting: "⏹ Aborting...",
    statusAborted: "Build cancelled by user.",
    statusPreparing: "Preparing...",
    statusExtracting: "Extracting frames ({cur}/{tot})...",
    statusCompiling: "Compiling blueprint...",
    statusCompleted: "✓ Completed and copied to clipboard! (Paste in Factorio with Ctrl+V)",
    statusPartCached: "✓ Part {p} ready in cache.",
    statusClipboardCopied: "✓ Blueprint copied to clipboard! (Paste in Factorio with Ctrl+V)",
    statusFileSaved: "✓ File saved successfully: {path}",
    statusError: "⚠️ Error: {msg}",
    
    titleDiagram: "ARCHITECTURAL DIAGRAM & PART SELECTOR",
    partTabBtn: "Part {p} ({combs} combs)",
    partTabBtnSimple: "Part {p}",
    zoomTooltip: "Interface Scale (Ctrl + Wheel)",
    zoomOutTitle: "Zoom Out (Ctrl -)",
    zoomInTitle: "Zoom In (Ctrl +)",
    zoomResetTitle: "Reset Zoom (Ctrl 0)",
    canvasHintBadge: "🔍 Ctrl + Wheel: Zoom interface in/out",
    
    canvasMonitorTitle: "📺 MONITOR DISPLAY",
    canvasMonitorLamps: "{w} x {h}  ({lamps} Lamps)",
    canvasPartIncludedSelected: "★ INCLUDED IN PART 1 (SELECTED)",
    canvasPartIncluded: "(Included in Part 1)",
    canvasRomRight: "RIGHT ROM",
    canvasRomLeft: "LEFT ROM",
    canvasRomTop: "TOP ROM",
    canvasRomBottom: "BOTTOM ROM",
    canvasDisabled: "(Disabled)",
    canvasCombsSuffix: "Combs",
    
    statTotalCombinators: "Total Combinators",
    statPartCombinators: "Part {p}: {combs} combs",
    statMonitorScreen: "Monitor Display",
    statMonitorLamps: "{lamps} Lamps",
    statVideoDuration: "Video & Duration",
    statVideoFrames: "{n} Frames",
    statStripesPacks: "Stripes & Packs",
    statStripesCount: "{n} Stripe{s}",
    statPacksCount: "{packs} Pack{s} ({fpp} f/pack)"
  },
  tr: {
    appTitle: "FACTORIO 2.0",
    appSubtitle: "VIDEO & ROM BLUEPRINT GENERATOR",
    secVideoSource: "Video / GIF Kaynağı",
    btnSelectVideo: "Video Seç",
    btnLoadDemo: "Demo Yükle",
    demoAnimName: "Dahili Demo Animasyon",
    activeLabel: "Aktif:",
    ratioWord: "Oran",
    framesWord: "Kare",
    
    secCircuitEngine: "Devre Motoru (Circuit Engine)",
    engineV3Desc: "16 kare/sinyal 2-bit gri tonlama, tek kombinatörlük TrueColor uyarlayıcı (* 5.5M), Selector saat.",
    engineV2Desc: "3 kare/pack 9-bit renk (27-bit paketleme), kompakt ROM mimarisi.",
    engineV1Desc: "1 kare/kombinatör 24-bit TrueColor RGB, doğrudan sinyal haritalama.",
    engineWarning: "Yüksek çözünürlük nedeniyle blueprint boyutu çok büyük olabilir.",
    
    secMonitorResolution: "Monitör Çözünürlüğü",
    lblHeight: "Yükseklik:",
    resSummaryTemplate: "Çözünürlük: {w} x {h} ({lamps} Lamba) • {ratio} Oran",
    
    secRomPlacement: "ROM Devresi Konumu",
    optHorizontal: "Yatay",
    optVertical: "Dikey",
    dirLeft: "◀ Sol",
    dirRight: "Sağ ▶",
    dirBothHoriz: "◀ Çift / Her İkisi ▶",
    dirTop: "▲ Üst",
    dirBottom: "Alt ▼",
    dirBothVert: "▲ Çift / Her İkisi ▼",
    
    chkCompactRomTitle: "Kompakt ROM (Önerilen)",
    chkCompactRomDesc: "Kombinatörler arası boşluğu sıfırlar (0 karo).",
    chkFillAllRowsTitle: "Tüm Satırları Doldur (Önerilen)",
    chkFillAllRowsDesc: "ROM kombinatörlerini ekran boyunca çok satırlı düzenler.",
    
    lblSubstationQuality: "Trafo Niteliği:",
    subQualityLegendary: "Legendary (Efsanevi)",
    subQualityEpic: "Epic (Epik)",
    subQualityRare: "Rare (Nadir)",
    subQualityUncommon: "Uncommon (Sıra Dışı)",
    subQualityNormal: "Normal (Standart)",
    subQualityNone: "Trafo Yok (Harici Güç / Sandbox)",
    
    secFpsAndFrames: "FPS ve Kare Sayısı",
    chkAllVideo: "Tüm Video",
    lblMaxFrames: "Maksimum Kare:",
    
    secRomSlicing: "ROM Parçalama (Modüler Dilimler)",
    lblPartCount: "Parça Sayısı:",
    partsCountBadge: "{n} Parça",
    
    btnGenerateSingle: "BLUEPRINT OLUŞTUR",
    btnGeneratePart: "PARÇA {part}/{total} OLUŞTUR",
    btnAbort: "İPTAL ET",
    btnSaveBlueprint: ".txt Kaydet",
    
    statusReady: "Hazır. Blueprint oluşturmak için butona basın.",
    statusAborting: "⏹ İptal ediliyor...",
    statusAborted: "Derleme kullanıcı tarafından iptal edildi.",
    statusPreparing: "Hazırlanıyor...",
    statusExtracting: "Kare ayıklanıyor ({cur}/{tot})...",
    statusCompiling: "Blueprint derleniyor...",
    statusCompleted: "✓ Tamamlandı ve panoya kopyalandı! (Factorio'da Ctrl+V ile yapıştırabilirsiniz)",
    statusPartCached: "✓ Parça {p} önbellekte hazır.",
    statusClipboardCopied: "✓ Blueprint panoya kopyalandı! (Factorio'da Ctrl+V ile yapıştırabilirsiniz)",
    statusFileSaved: "✓ Dosya başarıyla kaydedildi: {path}",
    statusError: "⚠️ Hata: {msg}",
    
    titleDiagram: "MİMARÎ ŞEMA VE PARÇA SEÇİCİ",
    partTabBtn: "Parça {p} ({combs} komb.)",
    partTabBtnSimple: "Parça {p}",
    zoomTooltip: "Tüm Arayüz Ölçeği (Ctrl + Tekerlek)",
    zoomOutTitle: "Arayüzü Küçült (Ctrl -)",
    zoomInTitle: "Arayüzü Büyüt (Ctrl +)",
    zoomResetTitle: "Arayüzü Sıfırla (Ctrl 0)",
    canvasHintBadge: "🔍 Ctrl + Tekerlek: Tüm Arayüzü Büyüt / Küçült",
    
    canvasMonitorTitle: "📺 MONİTÖR EKRANI",
    canvasMonitorLamps: "{w} x {h}  ({lamps} Lamba)",
    canvasPartIncludedSelected: "★ PARÇA 1'E DAHİL (SEÇİLİ)",
    canvasPartIncluded: "(Parça 1'e dahildir)",
    canvasRomRight: "SAĞ ROM",
    canvasRomLeft: "SOL ROM",
    canvasRomTop: "ÜST ROM",
    canvasRomBottom: "ALT ROM",
    canvasDisabled: "(Devre Dışı)",
    canvasCombsSuffix: "Komb.",
    
    statTotalCombinators: "Toplam Kombinatör",
    statPartCombinators: "Parça {p}: {combs} komb.",
    statMonitorScreen: "Monitör Ekranı",
    statMonitorLamps: "{lamps} Lamba",
    statVideoDuration: "Video & Süre",
    statVideoFrames: "{n} Kare",
    statStripesPacks: "Şerit & Paket",
    statStripesCount: "{n} Şerit",
    statPacksCount: "{packs} Paket ({fpp} k/pkt)"
  }
};

// Durum Yönetimi (State)
const state = {
  // Dil tercihi (Varsayılan: İngilizce)
  lang: localStorage.getItem("factorio_app_lang") || "en",

  // Medya bilgileri
  videoPath: "__demo__",
  videoFileName: "",
  origWidth: 16,
  origHeight: 16,
  videoFps: 5.0,
  videoTotalFrames: 16,
  videoDuration: 3.2,
  
  // Seçimler
  engine: "v3", // v3 (2-bit), v2 (9-bit), v1 (24-bit)
  targetHeight: 16,
  romDirection: "horizontal", // horizontal | vertical
  romPlacement: "horizontal_right", // horizontal_right, horizontal_left, horizontal_both, vertical_top, vertical_bottom, vertical_both
  compactRom: true,
  fillAllRows: true,
  substationQuality: "legendary",
  fps: 5,
  allVideo: true,
  maxFrames: 16,
  numParts: 1,
  selectedPartIdx: 0,
  
  // Görsel Şema Kamera (Pan & Zoom)
  zoom: 1.0,
  panX: 0,
  panY: 0,

  // Önbellek ve Sonuçlar
  isCompiling: false,
  estimatedStats: null,
  compiledBlueprints: {}, // partIdx -> { blueprint: string, meta: object }
  sliceHitboxes: [] // Canvas tıklama bölgeleri
};

function t(key, vars = {}) {
  const currentLang = state.lang || "en";
  let text = (i18n[currentLang] && i18n[currentLang][key]) || (i18n.en && i18n.en[key]) || key;
  for (const [k, v] of Object.entries(vars)) {
    text = text.replaceAll(`{${k}}`, v);
  }
  return text;
}

function formatNumber(num) {
  const locale = state.lang === "tr" ? "tr-TR" : "en-US";
  return (num || 0).toLocaleString(locale);
}

// DOM Elemanları
const el = {
  // Dil
  langSwitchContainer: document.getElementById("langSwitchContainer"),
  langButtons: document.querySelectorAll(".lang-btn"),

  // Dosya
  btnSelectFile: document.getElementById("btnSelectFile"),
  btnLoadDemo: document.getElementById("btnLoadDemo"),
  lblFileName: document.getElementById("lblFileName"),
  lblFileDetails: document.getElementById("lblFileDetails"),
  
  // Motor
  engineSegment: document.getElementById("engineSegment"),
  lblEngineDesc: document.getElementById("lblEngineDesc"),
  boxEngineWarning: document.getElementById("boxEngineWarning"),
  
  // Çözünürlük
  presetButtons: document.querySelectorAll(".preset-btn"),
  inputHeight: document.getElementById("inputHeight"),
  lblCalcResolution: document.getElementById("lblCalcResolution"),
  
  // ROM
  romDirectionGroup: document.getElementById("romDirectionGroup"),
  romPlacementGroup: document.getElementById("romPlacementGroup"),
  chkCompactRom: document.getElementById("chkCompactRom"),
  chkFillAllRows: document.getElementById("chkFillAllRows"),
  selSubstationQuality: document.getElementById("selSubstationQuality"),
  
  // FPS & Kare
  fpsButtonGroup: document.getElementById("fpsButtonGroup"),
  chkAllVideo: document.getElementById("chkAllVideo"),
  inputMaxFrames: document.getElementById("inputMaxFrames"),
  
  // Parçalama
  sliderParts: document.getElementById("sliderParts"),
  lblPartsCount: document.getElementById("lblPartsCount"),
  sliceTabsContainer: document.getElementById("sliceTabsContainer"),
  
  // Aksiyonlar
  btnGenerate: document.getElementById("btnGenerate"),
  lblGenerateText: document.getElementById("lblGenerateText"),
  btnAbort: document.getElementById("btnAbort"),
  btnSaveBlueprint: document.getElementById("btnSaveBlueprint"),
  lblStatusText: document.getElementById("lblStatusText"),
  lblProgressPct: document.getElementById("lblProgressPct"),
  progressFill: document.getElementById("progressFill"),
  
  // Canvas & Zoom
  diagramCanvas: document.getElementById("diagramCanvas"),
  canvasWrapper: document.getElementById("canvasWrapper"),
  btnZoomIn: document.getElementById("btnZoomIn"),
  btnZoomOut: document.getElementById("btnZoomOut"),
  btnZoomReset: document.getElementById("btnZoomReset"),
  lblZoomLevel: document.getElementById("lblZoomLevel"),
  zoomToolbar: document.getElementById("zoomToolbar"),
  lblCanvasHint: document.getElementById("lblCanvasHint"),
  
  // İstatistik Kartları
  valTotalCombinators: document.getElementById("valTotalCombinators"),
  valPartCombinators: document.getElementById("valPartCombinators"),
  valMonitorSize: document.getElementById("valMonitorSize"),
  valMonitorLamps: document.getElementById("valMonitorLamps"),
  valVideoFrames: document.getElementById("valVideoFrames"),
  valVideoFpsDuration: document.getElementById("valVideoFpsDuration"),
  valStripesPacks: document.getElementById("valStripesPacks"),
  valPacksTotal: document.getElementById("valPacksTotal")
};

// ==========================================================================
// C# WebView2 Köprüsü (Bridge Communication)
// ==========================================================================
function sendToHost(data) {
  if (window.chrome && window.chrome.webview) {
    window.chrome.webview.postMessage(data);
  } else {
    sendToHttpApi(data);
  }
}

async function sendToHttpApi(data) {
  try {
    const action = data.action;

    if (action === "select_file") {
      try {
        const resp = await fetch("/api/select_file", { method: "POST" });
        const res = await resp.json();
        if (res.success && res.info) {
          handleHostMessage(res);
          return;
        }
      } catch (e) {}

      let input = document.getElementById("browserFileInput");
      if (!input) {
        input = document.createElement("input");
        input.type = "file";
        input.id = "browserFileInput";
        input.accept = "video/*,.gif,.mp4,.webm,.avi,.mov,.mkv";
        input.style.display = "none";
        document.body.appendChild(input);
        input.addEventListener("change", () => {
          if (input.files && input.files[0]) {
            uploadBrowserFile(input.files[0]);
          }
        });
      }
      input.click();
      return;
    }

    if (action === "copy_clipboard") {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(data.text);
        handleHostMessage({ type: "clipboard_copied" });
      }
      return;
    }

    if (action === "save_file") {
      const blob = new Blob([data.content], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = data.defaultName || "blueprint.txt";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      handleHostMessage({ type: "file_saved", path: data.defaultName });
      return;
    }

    if (action === "set_ui_zoom" || action === "reset_ui_zoom") {
      let currentZoom = parseFloat(document.body.style.zoom || "1.0");
      if (action === "reset_ui_zoom") currentZoom = 1.0;
      else currentZoom = Math.min(3.0, Math.max(0.5, currentZoom + (data.delta || 0)));
      document.body.style.zoom = currentZoom;
      handleHostMessage({ type: "ui_zoom_changed", factor: currentZoom, percent: Math.round(currentZoom * 100) });
      return;
    }

    if (action === "compile") {
      const response = await fetch("/api/compile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data.params)
      });
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const msg = JSON.parse(line);
            handleHostMessage(msg);
          } catch (e) {}
        }
      }
      if (buffer.trim()) {
        try { handleHostMessage(JSON.parse(buffer)); } catch (e) {}
      }
      return;
    }

    const resp = await fetch(`/api/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data.params || data)
    });
    const res = await resp.json();
    handleHostMessage(res);
  } catch (err) {
    console.error("HTTP Bridge error:", err);
    handleHostMessage({ error: err.message });
  }
}

async function uploadBrowserFile(file) {
  try {
    updateProgress(t("statusPreparing"), 0.1);
    const resp = await fetch("/api/upload", {
      method: "POST",
      headers: {
        "X-Filename": encodeURIComponent(file.name),
        "Content-Type": file.type || "application/octet-stream"
      },
      body: file
    });
    const res = await resp.json();
    handleHostMessage(res);
  } catch (err) {
    showError("File upload failed: " + err.message);
  }
}

if (window.chrome && window.chrome.webview) {
  window.chrome.webview.addEventListener("message", (event) => {
    handleHostMessage(event.data);
  });
}

function handleHostMessage(msg) {
  if (!msg) return;
  
  if (msg.success && msg.info) {
    // Medya bilgisi geldi
    applyMediaInfo(msg.info);
  } else if (msg.type === "progress") {
    // Derleme ilerlemesi
    updateProgress(msg.msg, msg.fraction);
  } else if (msg.type === "result") {
    // Derleme tamamlandı
    handleCompileResult(msg);
  } else if (msg.type === "aborted") {
    handleAbortResult(msg);
  } else if (msg.type === "clipboard_copied") {
    handleClipboardResult(msg);
  } else if (msg.type === "file_saved") {
    handleFileSavedResult(msg);
  } else if (msg.type === "ui_zoom_changed") {
    handleUiZoomChanged(msg);
  } else if (msg.total_combinators !== undefined) {
    // İstatistik tahmini geldi
    applyEstimatedStats(msg);
  } else if (msg.error) {
    showError(msg.error);
  }
}

// ==========================================================================
// Başlatma ve Olay Dinleyicileri (Event Listeners)
// ==========================================================================
function init() {
  setupLanguageEvents();
  setupFileEvents();
  setupEngineEvents();
  setupResolutionEvents();
  setupRomPlacementEvents();
  setupFpsEvents();
  setupSlicingEvents();
  setupActionEvents();
  setupCanvasEvents();
  updateZoomUI();
  
  // Başlangıç dilini uygula (Varsayılan: İngilizce)
  setLanguage(state.lang);
  
  // Başlangıç durumu
  updateRomPlacementButtons();
  requestEstimateStats();
  window.addEventListener("resize", () => drawDiagram());
  
  // Host'tan demo bilgisini iste
  sendToHost({ action: "load_demo" });
}

// 0. Dil Yönetimi
function setupLanguageEvents() {
  if (el.langButtons) {
    el.langButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        const targetLang = btn.dataset.lang;
        if (targetLang && targetLang !== state.lang) {
          setLanguage(targetLang);
        }
      });
    });
  }
}

function setLanguage(lang) {
  state.lang = lang;
  try {
    localStorage.setItem("factorio_app_lang", lang);
  } catch (e) {
    // localStorage erişilemezse yoksay
  }
  
  // Dil butonlarını güncelle
  if (el.langButtons) {
    el.langButtons.forEach(btn => {
      if (btn.dataset.lang === lang) btn.classList.add("active");
      else btn.classList.remove("active");
    });
  }
  
  // HTML lang niteliği
  document.documentElement.lang = lang;
  
  // data-i18n nitelikli tüm etiketleri güncelle
  document.querySelectorAll("[data-i18n]").forEach(node => {
    const k = node.getAttribute("data-i18n");
    if (k) {
      node.textContent = t(k);
    }
  });

  // Dropdown seçeneklerini güncelle
  updateDropdownLanguage();

  // Toolbar & buton ipuçlarını güncelle
  if (el.zoomToolbar) el.zoomToolbar.title = t("zoomTooltip");
  if (el.btnZoomOut) el.btnZoomOut.title = t("zoomOutTitle");
  if (el.btnZoomIn) el.btnZoomIn.title = t("zoomInTitle");
  if (el.btnZoomReset) el.btnZoomReset.title = t("zoomResetTitle");

  // Durum ve metinleri yenile
  if (state.videoPath === "__demo__") {
    state.videoFileName = t("demoAnimName");
  }
  
  if (el.lblFileName) {
    el.lblFileName.textContent = `${t("activeLabel")} ${state.videoFileName || t("demoAnimName")}`;
  }
  
  updateEngineUI();
  updateRomPlacementButtons();
  updateResolutionDisplay();
  updateSliceTabs();
  updateGenerateButtonText();
  
  const p = state.selectedPartIdx;
  const hasBp = Boolean(state.compiledBlueprints[p]);
  if (hasBp) {
    el.lblStatusText.textContent = t("statusPartCached", { p: p + 1 });
  } else if (!state.isCompiling) {
    el.lblStatusText.textContent = t("statusReady");
  }

  if (state.estimatedStats) {
    applyEstimatedStats(state.estimatedStats);
  } else {
    requestEstimateStats();
  }
  
  drawDiagram();
}

function updateDropdownLanguage() {
  if (!el.selSubstationQuality) return;
  const opts = el.selSubstationQuality.options;
  for (let i = 0; i < opts.length; i++) {
    const opt = opts[i];
    const key = opt.getAttribute("data-i18n");
    if (key) {
      opt.textContent = t(key);
    }
  }
}

// 1. Dosya Olayları
function setupFileEvents() {
  el.btnSelectFile.addEventListener("click", () => {
    sendToHost({ action: "select_file" });
  });
  
  el.btnLoadDemo.addEventListener("click", () => {
    sendToHost({ action: "load_demo" });
  });

  // Tarayıcı ortamında sürükle & bırak (Linux, macOS & Web)
  window.addEventListener("dragover", (e) => {
    e.preventDefault();
    if (e.dataTransfer) {
      e.dataTransfer.dropEffect = "copy";
    }
  });

  window.addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      if (!window.chrome || !window.chrome.webview) {
        uploadBrowserFile(file);
      }
    }
  });
}

function getAspectRatioText(w, h) {
  if (!w || !h) return "1:1";
  function gcd(a, b) { return b === 0 ? a : gcd(b, a % b); }
  const g = gcd(w, h);
  const rw = Math.round(w / g);
  const rh = Math.round(h / g);
  if (rw <= 32 && rh <= 32) {
    return `${rw}:${rh}`;
  }
  return `${(w / h).toFixed(2)}:1`;
}

function applyMediaInfo(info) {
  state.videoPath = info.path;
  if (info.path === "__demo__") {
    state.videoFileName = t("demoAnimName");
  } else {
    state.videoFileName = info.filename || "Video";
  }
  
  state.origWidth = info.width || info.orig_w || 16;
  state.origHeight = info.height || info.orig_h || 16;
  state.videoFps = info.fps || 5.0;
  state.videoTotalFrames = info.total_frames || 16;
  state.videoDuration = info.duration || 3.2;
  
  const ratioText = getAspectRatioText(state.origWidth, state.origHeight);
  el.lblFileName.textContent = `${t("activeLabel")} ${state.videoFileName}`;
  el.lblFileDetails.textContent = `${state.origWidth}x${state.origHeight} (${ratioText} ${t("ratioWord")}) • ${state.videoTotalFrames} ${t("framesWord")} • ${state.videoFps} FPS • ${state.videoDuration}s`;
  
  // FPS seçeneklerini filtrele (video FPS'inden yüksek olanlar devre dışı)
  updateFpsAvailability();
  
  if (state.allVideo) {
    state.maxFrames = state.videoTotalFrames;
    el.inputMaxFrames.value = state.maxFrames;
  }
  
  updateResolutionDisplay();
  requestEstimateStats();
}

// 2. Devre Motoru Olayları
function setupEngineEvents() {
  const engineBtns = el.engineSegment.querySelectorAll(".segment-btn");
  engineBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      engineBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      
      state.engine = btn.dataset.engine;
      updateEngineUI();
      requestEstimateStats();
    });
  });
}

function updateEngineUI() {
  if (state.engine === "v3") {
    el.lblEngineDesc.textContent = t("engineV3Desc");
    el.boxEngineWarning.classList.add("hidden");
  } else if (state.engine === "v2") {
    el.lblEngineDesc.textContent = t("engineV2Desc");
    el.boxEngineWarning.classList.add("hidden");
  } else { // v1
    el.lblEngineDesc.textContent = t("engineV1Desc");
    el.boxEngineWarning.classList.remove("hidden");
  }
}

// 3. Monitör Çözünürlüğü Olayları
function setupResolutionEvents() {
  el.presetButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      el.presetButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      
      const h = parseInt(btn.dataset.height, 10);
      state.targetHeight = h;
      el.inputHeight.value = h;
      
      updateResolutionDisplay();
      requestEstimateStats();
    });
  });
  
  // Anlık input dinlenir
  el.inputHeight.addEventListener("input", () => {
    let val = parseInt(el.inputHeight.value, 10);
    if (isNaN(val) || val < 1) val = 1;
    if (val > 1080) val = 1080;
    
    state.targetHeight = val;
    
    // Preset butonlarını senkronize et
    el.presetButtons.forEach(btn => {
      if (parseInt(btn.dataset.height, 10) === val) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });
    
    updateResolutionDisplay();
    requestEstimateStats();
  });
}

function updateResolutionDisplay() {
  const calcW = Math.max(1, Math.round(state.targetHeight * (state.origWidth / Math.max(1, state.origHeight))));
  const lamps = calcW * state.targetHeight;
  const ratioText = getAspectRatioText(state.origWidth, state.origHeight);
  
  el.lblCalcResolution.textContent = t("resSummaryTemplate", {
    w: calcW,
    h: state.targetHeight,
    lamps: formatNumber(lamps),
    ratio: ratioText
  });
}

// 4. ROM Devresi Konumu Olayları
function setupRomPlacementEvents() {
  const dirBtns = el.romDirectionGroup.querySelectorAll(".segment-btn");
  dirBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      dirBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      
      state.romDirection = btn.dataset.dir;
      updateRomPlacementButtons();
      requestEstimateStats();
    });
  });
  
  el.chkCompactRom.addEventListener("change", () => {
    state.compactRom = el.chkCompactRom.checked;
    requestEstimateStats();
  });
  
  el.chkFillAllRows.addEventListener("change", () => {
    state.fillAllRows = el.chkFillAllRows.checked;
    requestEstimateStats();
  });
  
  el.selSubstationQuality.addEventListener("change", () => {
    state.substationQuality = el.selSubstationQuality.value;
    requestEstimateStats();
  });
}

function updateRomPlacementButtons() {
  el.romPlacementGroup.innerHTML = "";
  
  if (state.romDirection === "horizontal") {
    // Yatay: Sol, Sağ, Çift
    const options = [
      { id: "horizontal_left", label: t("dirLeft") },
      { id: "horizontal_right", label: t("dirRight"), isDefault: true },
      { id: "horizontal_both", label: t("dirBothHoriz") }
    ];
    
    if (!state.romPlacement.startsWith("horizontal")) {
      state.romPlacement = "horizontal_right";
    }
    
    options.forEach(opt => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "segment-btn" + (state.romPlacement === opt.id ? " active" : "");
      btn.textContent = opt.label;
      btn.addEventListener("click", () => {
        el.romPlacementGroup.querySelectorAll(".segment-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.romPlacement = opt.id;
        requestEstimateStats();
      });
      el.romPlacementGroup.appendChild(btn);
    });
  } else {
    // Dikey: Üst, Alt, Çift
    const options = [
      { id: "vertical_top", label: t("dirTop"), isDefault: true },
      { id: "vertical_bottom", label: t("dirBottom") },
      { id: "vertical_both", label: t("dirBothVert") }
    ];
    
    if (!state.romPlacement.startsWith("vertical")) {
      state.romPlacement = "vertical_top";
    }
    
    options.forEach(opt => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "segment-btn" + (state.romPlacement === opt.id ? " active" : "");
      btn.textContent = opt.label;
      btn.addEventListener("click", () => {
        el.romPlacementGroup.querySelectorAll(".segment-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.romPlacement = opt.id;
        requestEstimateStats();
      });
      el.romPlacementGroup.appendChild(btn);
    });
  }
}

// 5. FPS ve Kare Sayısı Olayları
function setupFpsEvents() {
  const fpsBtns = el.fpsButtonGroup.querySelectorAll(".fps-btn");
  fpsBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      if (btn.disabled) return;
      fpsBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      
      state.fps = parseInt(btn.dataset.fps, 10);
      requestEstimateStats();
    });
  });
  
  el.chkAllVideo.addEventListener("change", () => {
    state.allVideo = el.chkAllVideo.checked;
    el.inputMaxFrames.disabled = state.allVideo;
    if (state.allVideo) {
      state.maxFrames = state.videoTotalFrames;
      el.inputMaxFrames.value = state.maxFrames;
    }
    requestEstimateStats();
  });
  
  el.inputMaxFrames.addEventListener("input", () => {
    let val = parseInt(el.inputMaxFrames.value, 10);
    if (isNaN(val) || val < 1) val = 1;
    state.maxFrames = val;
    requestEstimateStats();
  });
}

function updateFpsAvailability() {
  const fpsBtns = el.fpsButtonGroup.querySelectorAll(".fps-btn");
  let activeDisabled = false;
  
  fpsBtns.forEach(btn => {
    const val = parseInt(btn.dataset.fps, 10);
    if (val > state.videoFps && val > 5) {
      btn.disabled = true;
      if (btn.classList.contains("active")) {
        activeDisabled = true;
      }
    } else {
      btn.disabled = false;
    }
  });
  
  if (activeDisabled) {
    let fallback = null;
    fpsBtns.forEach(btn => {
      if (!btn.disabled) fallback = btn;
    });
    if (fallback) {
      fpsBtns.forEach(b => b.classList.remove("active"));
      fallback.classList.add("active");
      state.fps = parseInt(fallback.dataset.fps, 10);
    }
  }
}

// 6. ROM Parçalama (Modüler Dilimler) Olayları
function setupSlicingEvents() {
  el.sliderParts.addEventListener("input", () => {
    const p = parseInt(el.sliderParts.value, 10);
    state.numParts = p;
    el.lblPartsCount.textContent = t("partsCountBadge", { n: p, s: p > 1 ? "s" : "" });
    if (state.selectedPartIdx >= p) {
      state.selectedPartIdx = 0;
    }
    updateSliceTabs();
    requestEstimateStats();
  });
}

function updateSliceTabs() {
  el.sliceTabsContainer.innerHTML = "";
  
  for (let i = 0; i < state.numParts; i++) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "slice-tab-btn" + (state.selectedPartIdx === i ? " active" : "");
    
    // Parça Kombinatör sayısı
    if (state.estimatedStats && state.estimatedStats.combs_per_part && state.estimatedStats.combs_per_part[i]) {
      const c = formatNumber(state.estimatedStats.combs_per_part[i]);
      btn.textContent = t("partTabBtn", { p: i + 1, combs: c });
    } else {
      btn.textContent = t("partTabBtnSimple", { p: i + 1 });
    }
    
    btn.addEventListener("click", () => {
      selectPart(i);
    });
    el.sliceTabsContainer.appendChild(btn);
  }
  
  updateGenerateButtonText();
}

function selectPart(idx) {
  state.selectedPartIdx = idx;
  el.sliceTabsContainer.querySelectorAll(".slice-tab-btn").forEach((b, i) => {
    if (i === idx) b.classList.add("active");
    else b.classList.remove("active");
  });
  
  updateGenerateButtonText();
  updateBlueprintActionButtons();
  drawDiagram();
}

function updateGenerateButtonText() {
  if (state.numParts > 1) {
    el.lblGenerateText.textContent = t("btnGeneratePart", { part: state.selectedPartIdx + 1, total: state.numParts });
  } else {
    el.lblGenerateText.textContent = t("btnGenerateSingle");
  }
}

function updateBlueprintActionButtons() {
  const p = state.selectedPartIdx;
  const hasBp = Boolean(state.compiledBlueprints[p]);
  el.btnSaveBlueprint.disabled = !hasBp;
  
  if (hasBp) {
    el.lblStatusText.textContent = t("statusPartCached", { p: p + 1 });
  }
}

// 7. Aksiyon Olayları (Derleme & İptal & Kaydetme)
function setupActionEvents() {
  el.btnGenerate.addEventListener("click", () => {
    startCompile();
  });

  el.btnAbort.addEventListener("click", () => {
    el.lblStatusText.textContent = t("statusAborting");
    el.lblStatusText.style.color = "#ef4444";
    sendToHost({ action: "abort" });
  });
  
  el.btnSaveBlueprint.addEventListener("click", () => {
    const p = state.selectedPartIdx;
    const item = state.compiledBlueprints[p];
    if (item && item.blueprint) {
      const defName = `blueprint_part_${p + 1}_of_${state.numParts}.txt`;
      sendToHost({ action: "save_file", content: item.blueprint, defaultName: defName });
    }
  });
}

function startCompile() {
  if (state.isCompiling) return;
  
  state.isCompiling = true;
  el.btnGenerate.disabled = true;
  el.btnAbort.style.display = "inline-flex";
  el.btnSaveBlueprint.disabled = true;
  
  updateProgress(t("statusPreparing"), 0.05);
  
  const payload = {
    video_path: state.videoPath,
    orig_w: state.origWidth,
    orig_h: state.origHeight,
    target_h: state.targetHeight,
    fps: state.fps,
    max_frames: state.allVideo ? state.videoTotalFrames : state.maxFrames,
    engine: state.engine,
    rom_mode: state.romPlacement,
    part_idx: state.selectedPartIdx,
    num_parts: state.numParts,
    compact_rom: state.compactRom,
    fill_all_rows: state.fillAllRows,
    substation_quality: state.substationQuality
  };
  
  sendToHost({ action: "compile", params: payload });
}

function updateProgress(msg, fraction) {
  // Python tarafından gelen metinleri çevir
  let localizedMsg = msg;
  if (msg.includes("Hazırlanıyor")) localizedMsg = t("statusPreparing");
  else if (msg.includes("Kare ayıklanıyor")) {
    const match = msg.match(/\((\d+)\/(\d+)\)/);
    if (match) localizedMsg = t("statusExtracting", { cur: match[1], tot: match[2] });
    else localizedMsg = t("statusPreparing");
  } else if (msg.includes("Blueprint derleniyor")) localizedMsg = t("statusCompiling");
  else if (msg.includes("Tamamlandı")) localizedMsg = t("statusCompleted");
  
  el.lblStatusText.textContent = localizedMsg;
  const pct = Math.min(100, Math.max(0, Math.round(fraction * 100)));
  el.lblProgressPct.textContent = `${pct}%`;
  el.progressFill.style.width = `${pct}%`;
}

function handleCompileResult(res) {
  state.isCompiling = false;
  el.btnGenerate.disabled = false;
  el.btnAbort.style.display = "none";
  
  if (res.success) {
    const p = res.part_idx;
    state.compiledBlueprints[p] = { blueprint: res.blueprint, meta: res.meta };
    
    updateProgress(t("statusCompleted"), 1.0);
    sendToHost({ action: "copy_clipboard", text: res.blueprint });
    updateBlueprintActionButtons();
  } else {
    updateProgress(t("statusError", { msg: "" }), 0.0);
    showError(res.error || "Compilation error occurred.");
  }
}

function handleAbortResult(msg) {
  state.isCompiling = false;
  el.btnGenerate.disabled = false;
  el.btnAbort.style.display = "none";
  updateProgress(t("statusAborted"), 0.0);
  el.lblStatusText.style.color = "#f59e0b";
}

function handleClipboardResult(res) {
  if (res.success) {
    el.lblStatusText.textContent = t("statusClipboardCopied");
    el.lblStatusText.style.color = "#10b981";
  }
}

function handleFileSavedResult(res) {
  if (res.success) {
    el.lblStatusText.textContent = t("statusFileSaved", { path: res.path });
  }
}

function handleUiZoomChanged(msg) {
  if (el.lblZoomLevel) {
    el.lblZoomLevel.textContent = `%${msg.percent || 100}`;
  }
  drawDiagram();
  requestAnimationFrame(() => drawDiagram());
  setTimeout(() => drawDiagram(), 60);
}

function showError(msg) {
  el.lblStatusText.textContent = t("statusError", { msg: msg });
  el.lblStatusText.style.color = "#ef4444";
  console.error("Error:", msg);
}

// ==========================================================================
// Anlık İstatistik Hesaplama (Estimate Stats)
// ==========================================================================
function requestEstimateStats() {
  const payload = {
    video_path: state.videoPath,
    orig_w: state.origWidth,
    orig_h: state.origHeight,
    target_h: state.targetHeight,
    engine: state.engine,
    fps: state.fps,
    total_frames: state.allVideo ? state.videoTotalFrames : state.maxFrames,
    rom_mode: state.romPlacement,
    num_parts: state.numParts,
    compact_rom: state.compactRom,
    fill_all_rows: state.fillAllRows,
    substation_quality: state.substationQuality
  };
  
  sendToHost({ action: "estimate_stats", params: payload });
}

function applyEstimatedStats(stats) {
  state.estimatedStats = stats;
  
  // Alt panel kartlarını güncelle
  el.valTotalCombinators.textContent = formatNumber(stats.total_combinators);
  if (stats.combs_per_part && stats.combs_per_part[state.selectedPartIdx]) {
    el.valPartCombinators.textContent = t("statPartCombinators", {
      p: state.selectedPartIdx + 1,
      combs: formatNumber(stats.combs_per_part[state.selectedPartIdx])
    });
  }
  
  el.valMonitorSize.textContent = `${stats.width} x ${stats.height}`;
  el.valMonitorLamps.textContent = t("statMonitorLamps", { lamps: formatNumber(stats.lamps) });
  
  el.valVideoFrames.textContent = t("statVideoFrames", { n: formatNumber(stats.total_frames) });
  const durSec = ((stats.total_frames || 0) / Math.max(1, state.fps)).toFixed(1);
  el.valVideoFpsDuration.textContent = `${state.fps} FPS • ${durSec}s`;
  
  const ns = stats.num_stripes || 1;
  el.valStripesPacks.textContent = t("statStripesCount", { n: ns, s: ns > 1 ? "s" : "" });
  
  const fpp = (state.engine === "v3" ? 16 : (state.engine === "v2" ? 3 : 1));
  const tp = stats.total_packs || 1;
  el.valPacksTotal.textContent = t("statPacksCount", { packs: tp, s: tp > 1 ? "s" : "", fpp: fpp });
  
  updateSliceTabs();
  drawDiagram();
}

// ==========================================================================
// İnteraktif Mimarî Şema (Canvas Rendering)
// ==========================================================================
function updateZoomUI() {
  if (el.lblZoomLevel) {
    el.lblZoomLevel.textContent = `%${Math.round(state.zoom * 100)}`;
  }
}

function setupCanvasEvents() {
  const canvas = el.diagramCanvas;
  const wrapper = el.canvasWrapper;
  if (!canvas || !wrapper) return;
  
  let isDragging = false;
  let hasDragged = false;
  let startX = 0;
  let startY = 0;
  let startPanX = 0;
  let startPanY = 0;

  // 1. Mouse Wheel: Ctrl ile basılıysa tüm arayüzü zoom'lar
  let wheelZoomTimer = null;
  wrapper.addEventListener("wheel", (evt) => {
    if (evt.ctrlKey) {
      clearTimeout(wheelZoomTimer);
      wheelZoomTimer = setTimeout(() => {
        drawDiagram();
      }, 40);
      return;
    }
    
    // Ctrl basılı değilse: Şemayı dikey kaydır (Pan)
    evt.preventDefault();
    state.panY -= evt.deltaY * 0.6;
    drawDiagram();
  }, { passive: false });

  // 2. Fare ile Sürükleyip Kaydırma (Pan)
  canvas.addEventListener("mousedown", (evt) => {
    if (evt.button === 0 || evt.button === 1) {
      isDragging = true;
      hasDragged = false;
      startX = evt.clientX;
      startY = evt.clientY;
      startPanX = state.panX;
      startPanY = state.panY;
      canvas.style.cursor = "grabbing";
    }
  });

  window.addEventListener("mousemove", (evt) => {
    if (!isDragging) return;
    const dx = evt.clientX - startX;
    const dy = evt.clientY - startY;
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
      hasDragged = true;
    }
    state.panX = startPanX + dx;
    state.panY = startPanY + dy;
    drawDiagram();
  });

  window.addEventListener("mouseup", () => {
    if (isDragging) {
      isDragging = false;
      canvas.style.cursor = "default";
    }
  });

  // 3. Tıklama ile Dilim / Parça Seçimi
  canvas.addEventListener("click", (evt) => {
    if (hasDragged) return;

    const rect = canvas.getBoundingClientRect();
    const mouseX = evt.clientX - rect.left;
    const mouseY = evt.clientY - rect.top;

    const cx = rect.width / 2;
    const cy = rect.height / 2;
    const worldX = (mouseX - cx - state.panX) + cx;
    const worldY = (mouseY - cy - state.panY) + cy;

    for (const hb of state.sliceHitboxes) {
      if (worldX >= hb.x && worldX <= hb.x + hb.w && worldY >= hb.y && worldY <= hb.y + hb.h) {
        selectPart(hb.partIdx);
        break;
      }
    }
  });

  // 4. Çift Tık ile Şema Konumunu Sıfırla
  canvas.addEventListener("dblclick", () => {
    state.panX = 0;
    state.panY = 0;
    drawDiagram();
  });

  // 5. Zoom Butonları
  if (el.btnZoomIn) {
    el.btnZoomIn.addEventListener("click", () => {
      sendToHost({ action: "set_ui_zoom", delta: 0.1 });
    });
  }
  if (el.btnZoomOut) {
    el.btnZoomOut.addEventListener("click", () => {
      sendToHost({ action: "set_ui_zoom", delta: -0.1 });
    });
  }
  if (el.btnZoomReset) {
    el.btnZoomReset.addEventListener("click", () => {
      sendToHost({ action: "reset_ui_zoom" });
    });
  }

  // 6. Kısayol Tuşları (Ctrl +, Ctrl -, Ctrl 0)
  window.addEventListener("keydown", (evt) => {
    if (evt.ctrlKey) {
      if (evt.key === "=" || evt.key === "+") {
        evt.preventDefault();
        sendToHost({ action: "set_ui_zoom", delta: 0.1 });
      } else if (evt.key === "-") {
        evt.preventDefault();
        sendToHost({ action: "set_ui_zoom", delta: -0.1 });
      } else if (evt.key === "0") {
        evt.preventDefault();
        sendToHost({ action: "reset_ui_zoom" });
      }
    }
  });

  // 7. Viewport & DPI Dinleyicileri
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", () => {
      drawDiagram();
    });
  }

  function listenDpi() {
    const mq = window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`);
    mq.addEventListener("change", () => {
      drawDiagram();
      listenDpi();
    }, { once: true });
  }
  listenDpi();

  // 8. ResizeObserver
  if (window.ResizeObserver) {
    const ro = new ResizeObserver(() => {
      drawDiagram();
    });
    ro.observe(wrapper);
  }
}

function drawDiagram() {
  const canvas = el.diagramCanvas;
  const wrapper = el.canvasWrapper;
  if (!canvas || !wrapper) return;
  
  const rect = wrapper.getBoundingClientRect();
  const width = Math.floor(rect.width);
  const height = Math.floor(rect.height);
  if (width <= 0 || height <= 0) return;
  
  // High-DPI Vektörel Çizim
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  canvas.style.width = width + "px";
  canvas.style.height = height + "px";

  const ctx = canvas.getContext("2d");
  ctx.resetTransform();
  ctx.scale(dpr, dpr);
  
  state.sliceHitboxes = [];
  
  // Arka plan temizle
  ctx.fillStyle = "#080b11";
  ctx.fillRect(0, 0, width, height);
  
  // Grid deseni
  ctx.strokeStyle = "rgba(255, 255, 255, 0.025)";
  ctx.lineWidth = 1;
  const gridSize = 24;
  const offsetX = ((width / 2 + state.panX) % gridSize + gridSize) % gridSize;
  const offsetY = ((height / 2 + state.panY) % gridSize + gridSize) % gridSize;
  for (let x = offsetX; x < width; x += gridSize) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }
  for (let y = offsetY; y < height; y += gridSize) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }
  
  // Kamera Pan Transformu
  ctx.save();
  const cx = width / 2;
  const cy = height / 2;
  ctx.translate(cx + state.panX, cy + state.panY);
  ctx.translate(-cx, -cy);
  
  const calcW = Math.max(1, Math.round(state.targetHeight * (state.origWidth / Math.max(1, state.origHeight))));
  const calcH = state.targetHeight;
  
  // Monitör ekran boyutlarını orantıla
  const maxMonW = Math.min(width * 0.44, 460);
  const maxMonH = Math.min(height * 0.48, 360);
  const monAspect = calcW / calcH;
  
  let monW, monH;
  if (monAspect > (maxMonW / maxMonH)) {
    monW = maxMonW;
    monH = Math.max(30, monW / monAspect);
  } else {
    monH = maxMonH;
    monW = Math.max(30, monH * monAspect);
  }
  
  const mx0 = cx - monW / 2;
  const my0 = cy - monH / 2;
  
  // 1. Monitör Çizimi
  const isP0Selected = (state.selectedPartIdx === 0);
  ctx.fillStyle = isP0Selected ? "#131f33" : "#0d1420";
  ctx.strokeStyle = isP0Selected ? "#f59e0b" : "#223147";
  ctx.lineWidth = isP0Selected ? 2.5 : 1.5;
  ctx.fillRect(mx0, my0, monW, monH);
  ctx.strokeRect(mx0, my0, monW, monH);
  
  // Monitör Tıklama Bölgesi (Parça 0)
  state.sliceHitboxes.push({ x: mx0, y: my0, w: monW, h: monH, partIdx: 0 });
  
  // Monitör İçi Metin
  ctx.fillStyle = isP0Selected ? "#38bdf8" : "#94a3b8";
  ctx.font = "bold 13px 'Segoe UI', sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(t("canvasMonitorTitle"), cx, cy - 12);
  
  ctx.fillStyle = isP0Selected ? "#f8fafc" : "#64748b";
  ctx.font = "bold 11px 'JetBrains Mono', monospace";
  ctx.fillText(`${calcW} x ${calcH}  (${formatNumber(calcW * calcH)} ${state.lang === 'tr' ? 'Lamba' : 'Lamps'})`, cx, cy + 6);
  
  ctx.fillStyle = isP0Selected ? "#f59e0b" : "#475569";
  ctx.font = "bold 9px 'Segoe UI', sans-serif";
  ctx.fillText(isP0Selected ? t("canvasPartIncludedSelected") : t("canvasPartIncluded"), cx, cy + 22);
  
  // 1.1 Çapa Trafosu Çizimi (Sol Üst)
  const isNoTrafo = (state.substationQuality === "none");
  const tfSize = 10;
  const tf1X = mx0 - tfSize - 4;
  const tf1Y = my0;
  
  // 1. Çapa Trafosu
  ctx.fillStyle = "#10b981";
  ctx.strokeStyle = "#34d399";
  ctx.lineWidth = 1.2;
  ctx.fillRect(tf1X, tf1Y, tfSize, tfSize);
  ctx.strokeRect(tf1X, tf1Y, tfSize, tfSize);
  
  if (!isNoTrafo) {
    // 2. Çapa Trafosu (Yalnızca trafo seçiliyken)
    const tf2Y = my0 - tfSize - 4;
    ctx.fillStyle = "#f59e0b";
    ctx.strokeStyle = "#fbbf24";
    ctx.fillRect(tf1X, tf2Y, tfSize, tfSize);
    ctx.strokeRect(tf1X, tf2Y, tfSize, tfSize);
    
    // Bakır kablo çizgisi
    ctx.strokeStyle = "#d97706";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(tf1X + tfSize / 2, tf1Y + tfSize / 2);
    ctx.lineTo(tf1X + tfSize / 2, tf2Y + tfSize / 2);
    ctx.stroke();
  }
  
  // 2. ROM Blokları Çizimi
  const romGap = state.compactRom ? 6 : 14;
  const sideRomW = Math.max(80, Math.min(180, (mx0 - 40)));
  const vertRomH = Math.max(50, Math.min(120, (my0 - 40)));
  
  const activeSides = {
    right: (state.romPlacement === "horizontal_right" || state.romPlacement === "horizontal_both"),
    left: (state.romPlacement === "horizontal_left" || state.romPlacement === "horizontal_both"),
    top: (state.romPlacement === "vertical_top" || state.romPlacement === "vertical_both"),
    bottom: (state.romPlacement === "vertical_bottom" || state.romPlacement === "vertical_both")
  };
  
  const romBoxes = {
    right: { x: mx0 + monW + romGap, y: my0, w: sideRomW, h: monH, isHoriz: true, label: t("canvasRomRight") },
    left: { x: mx0 - romGap - sideRomW, y: my0, w: sideRomW, h: monH, isHoriz: true, label: t("canvasRomLeft") },
    top: { x: mx0, y: my0 - romGap - vertRomH, w: monW, h: vertRomH, isHoriz: false, label: t("canvasRomTop") },
    bottom: { x: mx0, y: my0 + monH + romGap, w: monW, h: vertRomH, isHoriz: false, label: t("canvasRomBottom") }
  };
  
  for (const [side, box] of Object.entries(romBoxes)) {
    const isActive = activeSides[side];
    
    if (!isActive) {
      // Sönük devre dışı blok
      ctx.fillStyle = "rgba(185, 28, 28, 0.05)";
      ctx.strokeStyle = "rgba(239, 68, 68, 0.2)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.fillRect(box.x, box.y, box.w, box.h);
      ctx.strokeRect(box.x, box.y, box.w, box.h);
      ctx.setLineDash([]);
      
      ctx.fillStyle = "#7f1d1d";
      ctx.font = "bold 10px 'Segoe UI', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(`❌ ${box.label}`, box.x + box.w / 2, box.y + box.h / 2 - 4);
      ctx.fillStyle = "#5c2020";
      ctx.font = "9px 'Segoe UI', sans-serif";
      ctx.fillText(t("canvasDisabled"), box.x + box.w / 2, box.y + box.h / 2 + 10);
    } else {
      // Aktif ROM Bloğu: Dilimlere ayır
      ctx.fillStyle = "#0c1420";
      ctx.strokeStyle = "#0284c7";
      ctx.lineWidth = 1.5;
      ctx.fillRect(box.x, box.y, box.w, box.h);
      ctx.strokeRect(box.x, box.y, box.w, box.h);
      
      const nParts = state.numParts;
      
      for (let p = 0; p < nParts; p++) {
        let sx, sy, sw, sh;
        
        if (box.isHoriz) {
          const sliceW = box.w / nParts;
          if (side === "right") {
            sx = box.x + p * sliceW;
          } else { // left
            sx = box.x + (nParts - 1 - p) * sliceW;
          }
          sy = box.y;
          sw = sliceW;
          sh = box.h;
        } else {
          const sliceH = box.h / nParts;
          if (side === "bottom") {
            sy = box.y + p * sliceH;
          } else { // top
            sy = box.y + (nParts - 1 - p) * sliceH;
          }
          sx = box.x;
          sw = box.w;
          sh = sliceH;
        }
        
        const isSelected = (state.selectedPartIdx === p);
        
        ctx.fillStyle = isSelected ? "rgba(245, 158, 11, 0.22)" : "rgba(14, 165, 233, 0.10)";
        ctx.strokeStyle = isSelected ? "#f59e0b" : "#1e293b";
        ctx.lineWidth = isSelected ? 2 : 1;
        ctx.fillRect(sx + 2, sy + 2, sw - 4, sh - 4);
        ctx.strokeRect(sx + 2, sy + 2, sw - 4, sh - 4);
        
        // Tıklama Hitbox
        state.sliceHitboxes.push({ x: sx, y: sy, w: sw, h: sh, partIdx: p });
        
        let combCount = "?";
        if (state.estimatedStats && state.estimatedStats.combs_per_part && state.estimatedStats.combs_per_part[p]) {
          combCount = formatNumber(state.estimatedStats.combs_per_part[p]);
        }
        
        ctx.fillStyle = isSelected ? "#fbbf24" : "#94a3b8";
        ctx.font = "bold 11px 'Segoe UI', sans-serif";
        ctx.textAlign = "center";
        
        const textY = sy + sh / 2;
        ctx.fillText(`P${p + 1}`, sx + sw / 2, textY - 6);
        
        ctx.fillStyle = isSelected ? "#f8fafc" : "#cbd5e1";
        ctx.font = "bold 10px 'JetBrains Mono', monospace";
        ctx.fillText(`${combCount} ${t("canvasCombsSuffix")}`, sx + sw / 2, textY + 9);
      }
    }
  }

  // Kamera transformunu geri yükle
  ctx.restore();
}

// Başlat
window.addEventListener("DOMContentLoaded", init);
