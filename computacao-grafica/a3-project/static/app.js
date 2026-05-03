const captureForms = document.querySelectorAll("[data-capture-form]");

function setStatus(element, message, kind = "") {
  element.textContent = message;
  element.classList.remove("is-error", "is-success");
  if (kind) {
    element.classList.add(kind);
  }
}

function stopStream(video) {
  const stream = video.srcObject;
  if (!stream) {
    return;
  }

  for (const track of stream.getTracks()) {
    track.stop();
  }

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
      video: {
        facingMode: "user",
      },
      audio: false,
    });

    video.srcObject = stream;
    await video.play();
    setStatus(status, "Camera pronta. Capture as amostras necessarias.");
  } catch (error) {
    setStatus(status, "Nao foi possivel acessar a camera do navegador.", "is-error");
  }
}

function captureFrame(video) {
  if (!video.videoWidth || !video.videoHeight) {
    throw new Error("camera-not-ready");
  }

  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;

  const context = canvas.getContext("2d");
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.92);
}

for (const root of captureForms) {
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
    const isActive = Boolean(video.srcObject);
    startButton.textContent = isActive ? "Fechar camera" : "Abrir camera";
  }

  startButton.addEventListener("click", async () => {
    if (video.srcObject) {
      stopStream(video);
      updateCameraButton();
      setStatus(status, "Camera encerrada.");
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus(status, "Este navegador nao suporta captura de camera.", "is-error");
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
      setStatus(status, "Abra a camera e aguarde a imagem aparecer antes de capturar.", "is-error");
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
      setStatus(
        status,
        `Colete pelo menos ${minCaptures} capturas antes de enviar.`,
        "is-error",
      );
      return;
    }

    const payload = Object.fromEntries(new FormData(form).entries());
    payload.captures = captures;

    setStatus(status, "Enviando capturas para o servidor...");

    try {
      const response = await fetch(form.action, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      const body = await response.json();

      if (!response.ok) {
        setStatus(status, body.message || "Operacao falhou.", "is-error");
        return;
      }

      setStatus(status, body.message || "Operacao concluida com sucesso.", "is-success");
      captures = [];
      renderGallery(gallery, captures);
      setTimeout(() => {
        window.location.reload();
      }, 900);
    } catch (error) {
      setStatus(status, "Falha de comunicacao com o servidor Flask.", "is-error");
    }
  });

  window.addEventListener("beforeunload", () => {
    stopStream(video);
    updateCameraButton();
  });
}