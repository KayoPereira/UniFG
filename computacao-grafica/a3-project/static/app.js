// ── Utilitários compartilhados ──────────────────────────────────────────────

function setStatus(element, message, kind = "") {
  element.textContent = message;
  element.classList.remove("is-error", "is-success");
  if (kind) element.classList.add(kind);
}

function stopStream(video) {
  const stream = video.srcObject;
  if (!stream) return;
  for (const track of stream.getTracks()) track.stop();
  video.srcObject = null;
}

function renderGallery(gallery, captures) {
  gallery.innerHTML = "";
  for (const capture of captures) {
    const image = document.createElement("img");
    image.src = capture;
    image.alt = "Miniatura da captura facial";
    gallery.appendChild(image);
  }
}

async function startCamera(video, status) {
  stopStream(video);
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user" },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();
    setStatus(status, "Câmera pronta.");
  } catch {
    setStatus(status, "Não foi possível acessar a câmera do navegador.", "is-error");
  }
}

function captureFrame(video) {
  if (!video.videoWidth || !video.videoHeight) throw new Error("camera-not-ready");
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.92);
}

// ── Formulários de cadastro manual (admin) ───────────────────────────────────

for (const root of document.querySelectorAll("[data-capture-form]")) {
  const form = root.querySelector("form");
  const video = root.querySelector("[data-video]");
  const gallery = root.querySelector("[data-gallery]");
  const status = root.querySelector("[data-status]");
  const minCaptures = Number(root.dataset.minCaptures || 1);
  const startButton = root.querySelector("[data-start-camera]");
  const captureButton = root.querySelector("[data-capture]");
  const clearButton = root.querySelector("[data-clear-captures]");
  let captures = [];

  function updateCameraButton() {
    startButton.textContent = video.srcObject ? "Fechar câmera" : "Abrir câmera";
  }

  startButton.addEventListener("click", async () => {
    if (video.srcObject) {
      stopStream(video);
      updateCameraButton();
      setStatus(status, "Câmera encerrada.");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus(status, "Este navegador não suporta captura de câmera.", "is-error");
      return;
    }
    await startCamera(video, status);
    updateCameraButton();
  });

  captureButton.addEventListener("click", () => {
    try {
      captures = [...captures, captureFrame(video)];
      renderGallery(gallery, captures);
      setStatus(status, `Capturas coletadas: ${captures.length}/${minCaptures}.`);
    } catch {
      setStatus(status, "Abra a câmera e aguarde a imagem aparecer antes de capturar.", "is-error");
    }
  });

  clearButton.addEventListener("click", () => {
    captures = [];
    renderGallery(gallery, captures);
    setStatus(status, "Capturas removidas.");
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (captures.length < minCaptures) {
      setStatus(status, `Colete pelo menos ${minCaptures} capturas antes de enviar.`, "is-error");
      return;
    }
    const payload = Object.fromEntries(new FormData(form).entries());
    payload.captures = captures;
    setStatus(status, "Enviando capturas para o servidor...");
    try {
      const response = await fetch(form.action, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await response.json();
      if (!response.ok) {
        setStatus(status, body.message || "Operação falhou.", "is-error");
        return;
      }
      setStatus(status, body.message || "Operação concluída com sucesso.", "is-success");
      captures = [];
      renderGallery(gallery, captures);
      setTimeout(() => window.location.reload(), 900);
    } catch {
      setStatus(status, "Falha de comunicação com o servidor Flask.", "is-error");
    }
  });

  window.addEventListener("beforeunload", () => stopStream(video));
}

// ── Auto-scan com verificação de vivacidade (entrada / saída) ─────────────────
//
// Máquina de estados:
//   idle      → tenta reconhecer o rosto a cada 1,5 s
//   challenge → rosto reconhecido; aguarda inclinação de cabeça (10 s de prazo)
//   cooldown  → resultado exibido; pausa antes de reiniciar

const SCAN_INTERVAL_MS     = 1500;
const CHALLENGE_TIMEOUT_MS = 10_000;
const COOLDOWN_SUCCESS_MS  = 5_000;
const COOLDOWN_DENIED_MS   = 3_500;

for (const root of document.querySelectorAll("[data-auto-scan]")) {
  const video         = root.querySelector("[data-video]");
  const status        = root.querySelector("[data-status]");
  const indicator     = root.querySelector("[data-scan-indicator]");
  const resultOverlay = root.querySelector("[data-scan-overlay]");
  const overlayTitle  = root.querySelector("[data-overlay-title]");
  const overlayName   = root.querySelector("[data-overlay-name]");
  const overlayMsg    = root.querySelector("[data-overlay-msg]");
  const dotsCanvas    = root.querySelector("[data-dots-canvas]");
  const dotsCtx       = dotsCanvas ? dotsCanvas.getContext("2d") : null;
  const challengeInfo = root.querySelector("[data-challenge-info]");
  const challengeName = root.querySelector("[data-challenge-name]");
  const progressBar   = root.querySelector("[data-challenge-progress]");
  const mode          = root.dataset.scanMode;

  // ── Estado ────────────────────────────────────────────────────────────────
  let state            = "idle";  // "idle" | "challenge" | "cooldown"
  let busy             = false;
  let pending          = null;    // { employeeCode, employeeName, confidence }
  let challengeStart   = 0;
  let rafProgressId    = null;
  let rafDotsId        = null;
  let currentDirection = null;
  let anglePollId      = null;

  // ── Poll rápido de ângulo (apenas durante o desafio) ─────────────────────
  async function pollAngle() {
    if (state !== "challenge" || !video.srcObject || !video.videoWidth) return;
    let frame;
    try { frame = captureFrame(video); }
    catch { return; }
    try {
      const res  = await fetch("/api/attendance/angle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ captures: [frame] }),
      });
      const body = await res.json();
      if (body.angle != null) {
        const a = body.angle;
        // frame não-espelhado: inclinar direita → ângulo negativo; esquerda → positivo
        currentDirection = a < -2 ? "right" : a > 2 ? "left" : null;
      } else {
        currentDirection = null;
      }
    } catch {}
  }

  // ── Canvas: ring de bolinhas ao redor da face ────────────────────────────
  function resizeCanvas() {
    if (!dotsCanvas) return;
    dotsCanvas.width  = video.offsetWidth;
    dotsCanvas.height = video.offsetHeight;
  }

  function drawDots() {
    if (!dotsCtx || state !== "challenge") return;

    const t     = (Date.now() - challengeStart) / 1000;
    const w     = dotsCanvas.width;
    const h     = dotsCanvas.height;
    const cx    = w / 2;
    const cy    = h / 2;
    const ringR = Math.min(w, h) * 0.40;
    const dir   = currentDirection;

    dotsCtx.clearRect(0, 0, w, h);

    // Apenas dois clusters laterais — sem bolinhas no topo ou base.
    // deg: 0 = topo, sentido horário → 90 = direita (tela), 270 = esquerda (tela)
    // Conversão para ângulo de canvas: ang = (deg - 90) * π/180
    const clusters = [
      { side: "right", degs: [45, 67.5, 90, 112.5, 135] },
      { side: "left",  degs: [225, 247.5, 270, 292.5, 315] },
    ];

    for (const { side, degs } of clusters) {
      const active = side === dir;
      for (const deg of degs) {
        const ang = (deg - 90) * Math.PI / 180;
        const x = cx + Math.cos(ang) * ringR;
        const y = cy + Math.sin(ang) * ringR;

        if (active) {
          const pulse = 0.5 + 0.5 * Math.sin(t * Math.PI * 3); // ~1.5 Hz
          const dotR  = 5 + 3 * pulse;
          const alpha = 0.65 + 0.35 * pulse;

          // Halo difuso
          const grd = dotsCtx.createRadialGradient(x, y, 0, x, y, dotR * 3.5);
          grd.addColorStop(0, `rgba(255,255,255,${(0.45 * pulse).toFixed(2)})`);
          grd.addColorStop(1, "rgba(255,255,255,0)");
          dotsCtx.beginPath();
          dotsCtx.arc(x, y, dotR * 3.5, 0, Math.PI * 2);
          dotsCtx.fillStyle = grd;
          dotsCtx.fill();

          // Bolinha sólida
          dotsCtx.beginPath();
          dotsCtx.arc(x, y, dotR, 0, Math.PI * 2);
          dotsCtx.fillStyle = `rgba(255,255,255,${alpha.toFixed(2)})`;
          dotsCtx.fill();
        } else {
          dotsCtx.beginPath();
          dotsCtx.arc(x, y, 3.5, 0, Math.PI * 2);
          dotsCtx.fillStyle = "rgba(255,255,255,0.22)";
          dotsCtx.fill();
        }
      }
    }

    rafDotsId = requestAnimationFrame(drawDots);
  }

  function startDots() {
    currentDirection = null;
    resizeCanvas();
    if (rafDotsId) cancelAnimationFrame(rafDotsId);
    rafDotsId = requestAnimationFrame(drawDots);
  }

  function stopDots() {
    if (rafDotsId) cancelAnimationFrame(rafDotsId);
    rafDotsId = null;
    if (dotsCtx) dotsCtx.clearRect(0, 0, dotsCanvas.width, dotsCanvas.height);
    currentDirection = null;
  }

  // ── Barra de progresso ────────────────────────────────────────────────────
  function animateProgress() {
    if (state !== "challenge") return;
    const pct = Math.min(100, ((Date.now() - challengeStart) / CHALLENGE_TIMEOUT_MS) * 100);
    progressBar.style.width = `${100 - pct}%`;
    rafProgressId = requestAnimationFrame(animateProgress);
  }

  // ── Transições de UI ──────────────────────────────────────────────────────
  function showChallenge(name) {
    challengeName.textContent = name;
    challengeInfo.hidden = false;
    resultOverlay.hidden = true;
    indicator.dataset.state = "challenge";
    challengeStart = Date.now();
    startDots();
    animateProgress();
    if (anglePollId) clearInterval(anglePollId);
    anglePollId = setInterval(pollAngle, 300);
  }

  function hideChallenge() {
    stopDots();
    cancelAnimationFrame(rafProgressId);
    progressBar.style.width = "100%";
    challengeInfo.hidden = true;
    if (anglePollId) { clearInterval(anglePollId); anglePollId = null; }
  }

  function showResult(kind, title, name, msg) {
    hideChallenge();
    overlayTitle.textContent   = title;
    overlayName.textContent    = name;
    overlayMsg.textContent     = msg;
    resultOverlay.dataset.kind = kind;
    resultOverlay.hidden       = false;
    indicator.dataset.state    = "result";
  }

  function enterCooldown(ms) {
    state = "cooldown";
    busy  = false;
    setTimeout(() => {
      resultOverlay.hidden = true;
      delete resultOverlay.dataset.kind;
      delete indicator.dataset.state;
      state = "idle";
      setStatus(status, "Posicione o rosto na câmera.");
      indicator.dataset.state = "scanning";
    }, ms);
  }

  // ── Fase 1: reconhecimento ────────────────────────────────────────────────
  async function tryScan() {
    if (busy || state !== "idle") return;
    if (!video.srcObject || !video.videoWidth) return;
    busy = true;

    let frame;
    try { frame = captureFrame(video); }
    catch { busy = false; return; }

    try {
      const res  = await fetch("/api/attendance/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode, captures: [frame] }),
      });
      const body = await res.json();

      if (res.ok && body.status === "recognized") {
        pending = {
          employeeCode: body.employee.employee_code,
          employeeName: body.employee.full_name,
          confidence:   body.confidence,
        };
        state = "challenge";
        showChallenge(body.employee.full_name);
        setStatus(status, "Rosto identificado! Realize o desafio.");
      } else if (res.status === 409) {
        showResult("denied", "Acesso negado", "", body.message);
        enterCooldown(COOLDOWN_DENIED_MS);
        return;
      } else if (body.status === "unknown") {
        setStatus(status, "Rosto não identificado. Ajuste o posicionamento.");
      } else {
        setStatus(status, "Posicione o rosto na câmera.");
      }
    } catch {
      setStatus(status, "Erro de conexão. Tentando novamente...", "is-error");
    }

    busy = false;
  }

  // ── Fase 2: verificação de vivacidade ─────────────────────────────────────
  async function tryLiveness() {
    if (busy || state !== "challenge") return;

    if (Date.now() - challengeStart > CHALLENGE_TIMEOUT_MS) {
      hideChallenge();
      state = "idle";
      pending = null;
      indicator.dataset.state = "scanning";
      setStatus(status, "Tempo esgotado. Posicione o rosto novamente.");
      return;
    }

    busy = true;

    let frame;
    try { frame = captureFrame(video); }
    catch { busy = false; return; }

    try {
      const res  = await fetch("/api/attendance/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode,
          employee_code: pending.employeeCode,
          confidence:    pending.confidence,
          captures:      [frame],
        }),
      });
      const body = await res.json();

      if (res.ok && body.status === "success") {
        showResult("success", "Acesso liberado", body.employee.full_name, body.message);
        pending = null;
        enterCooldown(COOLDOWN_SUCCESS_MS);
        return;
      }

      if (res.status === 409) {
        showResult("denied", "Acesso negado", "", body.message);
        pending = null;
        enterCooldown(COOLDOWN_DENIED_MS);
        return;
      }

      // liveness_failed (422): pollAngle() já atualiza currentDirection em tempo real
    } catch {
      setStatus(status, "Erro de conexão. Tentando novamente...", "is-error");
    }

    busy = false;
  }

  // ── Loop principal ─────────────────────────────────────────────────────────
  function tick() {
    if (state === "idle")           tryScan();
    else if (state === "challenge") tryLiveness();
  }

  // ── Inicialização ──────────────────────────────────────────────────────────
  (async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus(status, "Este navegador não suporta câmera.", "is-error");
      return;
    }
    await startCamera(video, status);
    resizeCanvas();
    setStatus(status, "Posicione o rosto na câmera.");
    indicator.dataset.state = "scanning";
    setInterval(tick, SCAN_INTERVAL_MS);
  })();

  video.addEventListener("loadedmetadata", resizeCanvas);
  window.addEventListener("resize", resizeCanvas);
  window.addEventListener("beforeunload", () => stopStream(video));
}

// ── Filtro de logs (server-side com debounce) ────────────────────────────────

function _debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

(function () {
  const form = document.getElementById("filtroForm");
  if (!form) return;
  const inputs = form.querySelectorAll("input[type=text]");
  const submitDebounced = _debounce(() => form.submit(), 450);
  inputs.forEach(input => input.addEventListener("input", submitDebounced));
})();

function limparFiltrosFrontEnd() {
  const form = document.getElementById("filtroForm");
  if (!form) return;
  form.querySelectorAll("input[type=text]").forEach(i => { i.value = ""; });
  form.submit();
}
