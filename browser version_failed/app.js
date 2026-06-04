import { FFmpeg } from "https://cdn.jsdelivr.net/npm/@ffmpeg/ffmpeg@0.12.10/dist/esm/index.js";
import { fetchFile, toBlobURL } from "https://cdn.jsdelivr.net/npm/@ffmpeg/util@0.12.1/dist/esm/index.js";

const els = {
  fileInput: document.getElementById("fileInput"),
  dropZone: document.getElementById("dropZone"),
  pickedFile: document.getElementById("pickedFile"),
  convertBtn: document.getElementById("convertBtn"),
  downloadBtn: document.getElementById("downloadBtn"),
  resetBtn: document.getElementById("resetBtn"),
  status: document.getElementById("status"),
  progressText: document.getElementById("progressText"),
  progressBar: document.getElementById("progressBar"),
};

let ffmpeg = null;
let ffmpegLoaded = false;
let selectedFile = null;
let outputBlobUrl = null;
let outputFileName = "";
let busy = false;

function withTimeout(promise, ms, label) {
  return Promise.race([
    promise,
    new Promise((_, reject) => {
      setTimeout(() => reject(new Error(`${label}_timeout`)), ms);
    }),
  ]);
}

function setStatus(text) {
  els.status.textContent = text;
}

function setProgress(value) {
  const clamped = Math.min(Math.max(value, 0), 100);
  els.progressBar.style.width = `${clamped.toFixed(0)}%`;
  els.progressText.textContent = `Progress: ${clamped.toFixed(0)}%`;
}

function setBusyState(isBusy) {
  busy = isBusy;
  els.convertBtn.disabled = isBusy || !selectedFile;
  els.resetBtn.disabled = isBusy;
  els.fileInput.disabled = isBusy;
}

function clearOutputUrl() {
  if (outputBlobUrl) {
    URL.revokeObjectURL(outputBlobUrl);
    outputBlobUrl = null;
  }
}

function clearSelection() {
  selectedFile = null;
  clearOutputUrl();
  outputFileName = "";
  els.downloadBtn.disabled = true;
  els.fileInput.value = "";
  els.pickedFile.textContent = "No file selected.";
  setProgress(0);
  setStatus("Pick a .dav file to begin.");
  setBusyState(false);
}

function isDavFile(file) {
  return /\.dav$/i.test(file.name);
}

function chooseFile(file) {
  if (!file) return;

  if (!isDavFile(file)) {
    selectedFile = null;
    els.convertBtn.disabled = true;
    els.downloadBtn.disabled = true;
    setStatus("Please select a file with .dav extension.");
    els.pickedFile.textContent = `Selected: ${file.name} (unsupported extension)`;
    return;
  }

  selectedFile = file;
  clearOutputUrl();
  outputFileName = `${file.name.replace(/\.[^.]+$/, "")}.mp4`;
  els.pickedFile.textContent = `Selected: ${file.name}`;
  els.downloadBtn.disabled = true;
  setProgress(0);
  setStatus("Ready to convert.");
  setBusyState(false);
}

async function ensureFFmpegLoaded() {
  if (ffmpegLoaded) return;

  setStatus("Loading FFmpeg engine. First launch can take 10-20 seconds...");

  ffmpeg = new FFmpeg();

  ffmpeg.on("progress", ({ progress }) => {
    if (Number.isFinite(progress)) {
      const pct = Math.round(progress * 100);
      setProgress(Math.min(Math.max(pct, 0), 99));
    }
  });

  const baseURL = "https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.6/dist/esm";
  const classWorkerURL = "https://cdn.jsdelivr.net/npm/@ffmpeg/ffmpeg@0.12.10/dist/esm/worker.js";
  await withTimeout(
    ffmpeg.load({
      coreURL: await toBlobURL(`${baseURL}/ffmpeg-core.js`, "text/javascript"),
      wasmURL: await toBlobURL(`${baseURL}/ffmpeg-core.wasm`, "application/wasm"),
      classWorkerURL: await toBlobURL(classWorkerURL, "text/javascript"),
    }),
    45000,
    "ffmpeg_load",
  );

  ffmpegLoaded = true;
}

async function runConversion(inputName, outputName) {
  const baseArgs = [
    "-i",
    inputName,
    "-c:v",
    "libx264",
    "-preset",
    "veryfast",
    "-crf",
    "23",
    "-movflags",
    "+faststart",
    "-pix_fmt",
    "yuv420p",
  ];

  try {
    await ffmpeg.exec([...baseArgs, "-c:a", "aac", "-b:a", "128k", outputName]);
  } catch {
    await ffmpeg.exec([...baseArgs, "-an", outputName]);
  }
}

async function convertSelectedFile() {
  if (!selectedFile || busy) return;

  setBusyState(true);
  setProgress(1);

  try {
    await ensureFFmpegLoaded();
    setStatus("Preparing input file...");

    const inputExt = selectedFile.name.split(".").pop()?.toLowerCase() || "dav";
    const inputName = `input.${inputExt}`;
    const outputName = "converted.mp4";

    await ffmpeg.writeFile(inputName, await fetchFile(selectedFile));

    setStatus("Converting to MP4...");
    await runConversion(inputName, outputName);

    const data = await ffmpeg.readFile(outputName);
    clearOutputUrl();
    outputBlobUrl = URL.createObjectURL(new Blob([data.buffer], { type: "video/mp4" }));

    setProgress(100);
    setStatus("Done. MP4 is ready to download.");
    els.downloadBtn.disabled = false;
  } catch (error) {
    console.error(error);
    if (String(error).includes("ffmpeg_load_timeout")) {
      setStatus("FFmpeg engine timed out in this browser. Use terminal ffmpeg fallback in README.");
    } else {
      setStatus("Conversion failed. File may be encrypted or unsupported by browser FFmpeg.");
    }
    setProgress(0);
  } finally {
    setBusyState(false);
  }
}

function wireDropZone() {
  const preventDefaults = (event) => {
    event.preventDefault();
    event.stopPropagation();
  };

  ["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
    els.dropZone.addEventListener(eventName, preventDefaults);
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    els.dropZone.addEventListener(eventName, () => {
      els.dropZone.classList.add("dragging");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    els.dropZone.addEventListener(eventName, () => {
      els.dropZone.classList.remove("dragging");
    });
  });

  els.dropZone.addEventListener("drop", (event) => {
    const file = event.dataTransfer?.files?.[0];
    chooseFile(file);
  });
}

els.fileInput.addEventListener("change", (event) => {
  chooseFile(event.target.files?.[0]);
});

els.convertBtn.addEventListener("click", async () => {
  await convertSelectedFile();
});

els.downloadBtn.addEventListener("click", () => {
  if (!outputBlobUrl) return;

  const anchor = document.createElement("a");
  anchor.href = outputBlobUrl;
  anchor.download = outputFileName || "converted.mp4";
  anchor.click();
});

els.resetBtn.addEventListener("click", () => {
  if (busy) return;
  clearSelection();
});

wireDropZone();
clearSelection();
