"""
Prime Land Solutions LLC — Video/Photo Upload Web UI
A simple local web server that lets you drag-and-drop videos or photos
directly into the browser, then the agent edits and exports them.

Run:
    python web_ui.py
Then open: http://localhost:8080
"""

from __future__ import annotations
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).parent))

INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output")
INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Job status store: { job_id: { status, files, outputs, error } }
JOBS: dict = {}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv"}

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Prime Land Solutions — Video Editor</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #111; color: #eee; min-height: 100vh; }
  header { background: #1a1a1a; border-bottom: 3px solid #D4890A;
           padding: 18px 32px; display: flex; align-items: center; gap: 16px; }
  header h1 { font-size: 1.4rem; color: #D4890A; letter-spacing: 1px; }
  header p  { font-size: 0.85rem; color: #888; margin-top: 2px; }
  .container { max-width: 860px; margin: 40px auto; padding: 0 24px; }

  .drop-zone {
    border: 2px dashed #D4890A; border-radius: 14px;
    padding: 60px 32px; text-align: center; cursor: pointer;
    transition: background 0.2s;
  }
  .drop-zone.hover { background: #1f1a10; }
  .drop-zone h2 { font-size: 1.3rem; color: #D4890A; margin-bottom: 8px; }
  .drop-zone p  { color: #888; font-size: 0.9rem; }
  .drop-zone input { display: none; }

  .options { margin-top: 28px; display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .options label { display: block; font-size: 0.8rem; color: #888; margin-bottom: 6px; }
  .options input, .options select {
    width: 100%; padding: 10px 14px;
    background: #1a1a1a; border: 1px solid #333; border-radius: 8px;
    color: #eee; font-size: 0.95rem;
  }
  .options .full { grid-column: 1 / -1; }

  .platform-grid { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }
  .platform-grid label { display: flex; align-items: center; gap: 6px;
    background: #1a1a1a; border: 1px solid #333; border-radius: 8px;
    padding: 8px 14px; cursor: pointer; font-size: 0.85rem; }
  .platform-grid input[type=checkbox]:checked + span { color: #D4890A; }

  .btn { margin-top: 28px; width: 100%; padding: 16px;
    background: #D4890A; color: #111; font-weight: 700; font-size: 1.05rem;
    border: none; border-radius: 10px; cursor: pointer; letter-spacing: 0.5px; }
  .btn:hover { background: #e8990f; }
  .btn:disabled { background: #555; color: #888; cursor: not-allowed; }

  #file-list { margin-top: 16px; }
  .file-item { background: #1a1a1a; border-radius: 8px; padding: 10px 16px;
    margin-bottom: 8px; font-size: 0.85rem; display: flex;
    justify-content: space-between; align-items: center; }
  .file-item .tag { font-size: 0.7rem; background: #D4890A22;
    color: #D4890A; padding: 2px 8px; border-radius: 12px; }

  #status-box { margin-top: 32px; }
  .job { background: #1a1a1a; border-radius: 12px; padding: 20px 24px;
    margin-bottom: 16px; }
  .job h3 { font-size: 0.95rem; margin-bottom: 10px; }
  .progress { height: 6px; background: #333; border-radius: 3px; overflow: hidden; }
  .progress-bar { height: 100%; background: #D4890A;
    transition: width 0.4s; border-radius: 3px; }
  .output-link { display: inline-block; margin-top: 8px; margin-right: 12px;
    color: #D4890A; font-size: 0.85rem; text-decoration: none; }
  .output-link:hover { text-decoration: underline; }
  .status-badge { font-size: 0.75rem; padding: 3px 10px; border-radius: 12px; }
  .status-badge.running { background: #1a3a5c; color: #6ac; }
  .status-badge.done    { background: #1a3a1a; color: #6c6; }
  .status-badge.error   { background: #3a1a1a; color: #c66; }
</style>
</head>
<body>
<header>
  <div>
    <h1>PRIME LAND SOLUTIONS LLC</h1>
    <p>AI Video Editing Agent — Upload videos or photos to create social media content</p>
  </div>
</header>
<div class="container">

  <div class="drop-zone" id="drop-zone">
    <h2>Drag & Drop Videos or Photos Here</h2>
    <p>Or click to browse files</p>
    <p style="margin-top:12px;font-size:0.78rem;color:#555;">
      Supported: MP4, MOV, AVI, MKV, JPG, PNG, WEBP
    </p>
    <input type="file" id="file-input" multiple
      accept="video/*,image/jpeg,image/png,image/webp">
  </div>
  <div id="file-list"></div>

  <div class="options">
    <div>
      <label>Content Type / Topic</label>
      <select id="topic">
        <option value="dirtwork">Dirt Work (General)</option>
        <option value="gravel driveway">Gravel Driveway</option>
        <option value="trenching">Trenching</option>
        <option value="drainage installation">Drainage Installation</option>
        <option value="land clearing">Land Clearing</option>
        <option value="excavation">Excavation</option>
        <option value="before and after">Before &amp; After Transformation</option>
      </select>
    </div>
    <div>
      <label>Caption Style</label>
      <select id="caption-style">
        <option value="bold_bottom">Bold Bottom (TikTok style)</option>
        <option value="center_pop">Center Pop (YouTube style)</option>
      </select>
    </div>
    <div class="full">
      <label>Export For (select all that apply):</label>
      <div class="platform-grid">
        <label><input type="checkbox" value="instagram_reel" checked>
          <span>Instagram Reel</span></label>
        <label><input type="checkbox" value="tiktok" checked>
          <span>TikTok</span></label>
        <label><input type="checkbox" value="facebook_reel" checked>
          <span>Facebook Reel</span></label>
        <label><input type="checkbox" value="youtube">
          <span>YouTube (Full)</span></label>
        <label><input type="checkbox" value="youtube_short">
          <span>YouTube Short</span></label>
        <label><input type="checkbox" value="facebook_feed">
          <span>Facebook Feed</span></label>
      </div>
    </div>
  </div>

  <button class="btn" id="submit-btn" disabled>Upload &amp; Edit Videos</button>

  <div id="status-box"></div>
</div>

<script>
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const fileList  = document.getElementById('file-list');
const submitBtn = document.getElementById('submit-btn');
const statusBox = document.getElementById('status-box');
let selectedFiles = [];

dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('hover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('hover'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('hover');
  addFiles(Array.from(e.dataTransfer.files));
});
fileInput.addEventListener('change', () => addFiles(Array.from(fileInput.files)));

function addFiles(files) {
  files.forEach(f => { if (!selectedFiles.find(x => x.name === f.name)) selectedFiles.push(f); });
  renderFileList();
}

function renderFileList() {
  fileList.innerHTML = selectedFiles.map((f, i) => {
    const type = f.type.startsWith('video') ? 'video' : 'photo';
    const size = (f.size / 1024 / 1024).toFixed(1) + ' MB';
    return `<div class="file-item">
      <span>${f.name} <small style="color:#555">${size}</small></span>
      <span class="tag">${type}</span>
    </div>`;
  }).join('');
  submitBtn.disabled = selectedFiles.length === 0;
}

function getPlatforms() {
  return Array.from(document.querySelectorAll('.platform-grid input:checked'))
    .map(cb => cb.value);
}

submitBtn.addEventListener('click', async () => {
  const platforms = getPlatforms();
  if (!platforms.length) { alert('Select at least one platform.'); return; }

  submitBtn.disabled = true;
  submitBtn.textContent = 'Uploading...';

  const formData = new FormData();
  selectedFiles.forEach(f => formData.append('files', f));
  formData.append('topic', document.getElementById('topic').value);
  formData.append('platforms', JSON.stringify(platforms));
  formData.append('caption_style', document.getElementById('caption-style').value);

  const resp = await fetch('/upload', { method: 'POST', body: formData });
  const data = await resp.json();

  submitBtn.textContent = 'Upload & Edit Videos';
  submitBtn.disabled = false;

  if (data.job_id) {
    addJobCard(data.job_id, selectedFiles.map(f=>f.name), platforms);
    selectedFiles = [];
    renderFileList();
    pollJob(data.job_id);
  } else {
    alert('Upload error: ' + (data.error || 'unknown'));
  }
});

function addJobCard(jobId, files, platforms) {
  const div = document.createElement('div');
  div.className = 'job';
  div.id = 'job-' + jobId;
  div.innerHTML = `
    <h3>Job: ${jobId.slice(0,8)}...
      <span class="status-badge running" id="badge-${jobId}">Running</span>
    </h3>
    <p style="font-size:0.8rem;color:#666;margin-bottom:12px">${files.join(', ')}</p>
    <div class="progress"><div class="progress-bar" id="bar-${jobId}" style="width:5%"></div></div>
    <div id="outputs-${jobId}" style="margin-top:12px"></div>`;
  statusBox.prepend(div);
}

function pollJob(jobId) {
  const iv = setInterval(async () => {
    const r = await fetch('/status/' + jobId);
    const d = await r.json();
    const bar = document.getElementById('bar-' + jobId);
    const badge = document.getElementById('badge-' + jobId);
    const outputs = document.getElementById('outputs-' + jobId);

    if (d.status === 'running') {
      bar.style.width = (d.progress || 30) + '%';
    } else if (d.status === 'done') {
      bar.style.width = '100%';
      badge.className = 'status-badge done';
      badge.textContent = 'Done';
      clearInterval(iv);
      if (d.outputs) {
        outputs.innerHTML = Object.entries(d.outputs).map(([platform, info]) =>
          info.status === 'success'
            ? `<a class="output-link" href="/download/${jobId}/${platform}">
                ⬇ ${info.label || platform}</a>`
            : `<span style="color:#c66;font-size:0.8rem">${platform}: error</span>`
        ).join('');
      }
    } else if (d.status === 'error') {
      bar.style.width = '100%';
      bar.style.background = '#c44';
      badge.className = 'status-badge error';
      badge.textContent = 'Error';
      outputs.innerHTML = `<p style="color:#c66;font-size:0.85rem">${d.error}</p>`;
      clearInterval(iv);
    }
  }, 2000);
}
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence default logging

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._send(200, HTML.encode(), "text/html")

        elif path.startswith("/status/"):
            job_id = path.split("/")[-1]
            job = JOBS.get(job_id, {"status": "not_found"})
            self._send(200, json.dumps(job).encode(), "application/json")

        elif path.startswith("/download/"):
            parts = path.split("/")
            if len(parts) >= 4:
                job_id = parts[2]
                platform = parts[3]
                job = JOBS.get(job_id, {})
                outputs = job.get("outputs", {})
                info = outputs.get(platform, {})
                file_path = info.get("path", "")
                if file_path and os.path.isfile(file_path):
                    with open(file_path, "rb") as f:
                        data = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Disposition",
                                     f'attachment; filename="{Path(file_path).name}"')
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
            self._send(404, b"Not found", "text/plain")
        else:
            self._send(404, b"Not found", "text/plain")

    def do_POST(self):
        if self.path == "/upload":
            self._handle_upload()
        else:
            self._send(404, b"Not found", "text/plain")

    def _handle_upload(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send(400, b'{"error":"expected multipart/form-data"}', "application/json")
            return

        # Extract boundary from Content-Type header
        boundary = None
        for part in content_type.split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part[len("boundary="):].strip().encode()
                break

        if not boundary:
            self._send(400, b'{"error":"missing boundary"}', "application/json")
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)

        # Parse multipart body using email stdlib (no deprecated cgi needed)
        import email
        from email import policy as email_policy

        # email.message_from_bytes needs a full MIME message with headers
        msg_bytes = (
            f'Content-Type: {content_type}\r\n\r\n'.encode() + raw
        )
        msg = email.message_from_bytes(msg_bytes)

        fields: dict = {}      # text fields  → str
        files_info: list = []  # file parts   → (filename, bytes)

        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            cd = part.get("Content-Disposition", "")
            if not cd:
                continue

            # Parse Content-Disposition params
            cd_params: dict = {}
            for seg in cd.split(";"):
                seg = seg.strip()
                if "=" in seg:
                    k, v = seg.split("=", 1)
                    cd_params[k.strip().lower()] = v.strip().strip('"')

            name = cd_params.get("name", "")
            filename = cd_params.get("filename", "")
            payload = part.get_payload(decode=True) or b""

            if filename:
                files_info.append((filename, payload))
            elif name:
                fields[name] = payload.decode("utf-8", errors="replace")

        topic = fields.get("topic", "dirtwork")
        platforms_raw = fields.get("platforms", '["instagram_reel"]')
        try:
            platforms = json.loads(platforms_raw)
        except json.JSONDecodeError:
            platforms = ["instagram_reel"]
        caption_style = fields.get("caption_style", "bold_bottom")

        if not files_info:
            self._send(400, b'{"error":"no files received"}', "application/json")
            return

        job_id = str(uuid.uuid4())
        job_input_dir = INPUT_DIR / job_id
        job_input_dir.mkdir(parents=True)

        saved_paths = []
        for i, (fname, data) in enumerate(files_info):
            safe_name = Path(fname).name if fname else f"file_{i}"
            dest = job_input_dir / safe_name
            with open(dest, "wb") as f:
                f.write(data)
            saved_paths.append(str(dest))

        JOBS[job_id] = {
            "status": "running",
            "progress": 5,
            "files": saved_paths,
            "platforms": platforms,
            "topic": topic,
            "caption_style": caption_style,
            "outputs": {},
            "error": None,
        }

        # Run agent in background thread
        threading.Thread(
            target=_run_job,
            args=(job_id,),
            daemon=True,
        ).start()

        self._send(200, json.dumps({"job_id": job_id}).encode(), "application/json")

    def _send(self, code, body, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def _run_job(job_id: str):
    """Background thread: runs the appropriate agent for the uploaded files."""
    job = JOBS[job_id]
    try:
        saved_paths = job["files"]
        platforms = job["platforms"]
        topic = job["topic"]
        caption_style = job["caption_style"]

        images = [p for p in saved_paths if Path(p).suffix.lower() in IMAGE_EXTS]
        videos = [p for p in saved_paths if Path(p).suffix.lower() in VIDEO_EXTS]

        job["progress"] = 15
        outputs = {}

        if videos:
            # Use the video editing agent
            from agent import VideoEditingAgent
            agent = VideoEditingAgent()
            platforms_str = ", ".join(platforms)
            request = (
                f"Edit this video for Prime Land Solutions LLC.\n"
                f"Video files: {', '.join(videos)}\n"
                f"Content topic: {topic}\n"
                f"Target platforms: {platforms_str}\n"
                f"Caption style: {caption_style}\n"
                "Steps: get video info, transcribe audio, select clips, "
                "choose music, choose CTA, then render_video for the specified platforms.\n"
                f"Output base filename: prime_land_{job_id[:8]}"
            )
            job["progress"] = 25
            agent.run(request)
            # Collect outputs from exporter
            for platform in platforms:
                out_path = str(OUTPUT_DIR / f"prime_land_{job_id[:8]}_{platform}.mp4")
                if os.path.isfile(out_path):
                    outputs[platform] = {
                        "status": "success",
                        "path": out_path,
                        "label": __import__("config").PLATFORMS[platform]["label"],
                    }
                else:
                    outputs[platform] = {"status": "error", "error": "File not generated"}

        if images:
            # Use the photo agent
            from photo_agent import PhotoVideoAgent
            photo_agent = PhotoVideoAgent()
            job["progress"] = 40
            result = photo_agent.run(
                photo_paths=images,
                platforms=platforms,
                topic=topic,
                output_dir=str(OUTPUT_DIR),
                base_name=f"prime_land_{job_id[:8]}",
            )
            outputs.update(result.get("outputs", {}))

        job["progress"] = 100
        job["status"] = "done"
        job["outputs"] = outputs

    except Exception as e:
        import traceback
        traceback.print_exc()
        job["status"] = "error"
        job["error"] = str(e)


def main():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"\n{'='*60}")
    print(f"  PRIME LAND SOLUTIONS LLC — Video Editing Agent")
    print(f"{'='*60}")
    print(f"  Open in your browser:  http://localhost:{port}")
    print(f"  Press Ctrl+C to stop.\n")
    print("  TRANSFERRING VIDEOS FROM iPHONE:")
    print("  ─────────────────────────────────────────────────────")
    print("  Option A — AirDrop (easiest):")
    print("    1. On iPhone: open Photos, select video, tap Share")
    print("    2. Tap AirDrop → select your Mac")
    print("    3. Video lands in ~/Downloads — drag into the browser")
    print()
    print("  Option B — USB cable:")
    print("    1. Plug iPhone into Mac with cable")
    print("    2. Open Finder → click iPhone → Files → drag video out")
    print("    3. Drag the video file into the browser at localhost:8080")
    print()
    print("  Option C — iCloud:")
    print("    1. On iPhone: share video → Save to Files → iCloud Drive")
    print("    2. On Mac: open Finder → iCloud Drive → drag into browser")
    print(f"{'='*60}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
