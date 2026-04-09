"""
app.py — Flask Web App

Frontend simple con:
- Formulario de investigación (empresa, web, PDF, API key)
- Streaming de progreso en tiempo real (SSE)
- Visualización del reporte HTML generado
- Chat interactivo con Claude sobre los resultados

Arrancar:
    python app.py
    → http://127.0.0.1:5000
"""

import json
import os
import queue
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from flask import Flask, Response, jsonify, render_template, request, send_file

from config import ANTHROPIC_MODELS, FLASK_DEBUG, FLASK_HOST, FLASK_PORT, OUTPUT_DIR
from llm.synthesis import LLMSynthesizer
from main import ResearchSystem

# ──────────────────────────────────────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────────────────────────────────────

app = Flask(__name__, template_folder="web_templates")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB upload limit

# Almacén en memoria de tareas activas
# {task_id: {"queue": Queue, "status": str, "result": dict|None}}
_tasks: dict[str, dict] = {}

# Historial de conversaciones por sesión
# {session_id: {"company": str, "consolidated": dict, "history": list}}
_sessions: dict[str, dict] = {}

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


# ──────────────────────────────────────────────────────────────────────────────
# Rutas principales
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/models")
def get_models():
    """Devuelve los modelos disponibles."""
    return jsonify(ANTHROPIC_MODELS)


# ──────────────────────────────────────────────────────────────────────────────
# API: lanzar investigación
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/research", methods=["POST"])
def start_research():
    """
    Inicia una investigación en un hilo background.
    Acepta multipart/form-data (para subida de PDF) o JSON.

    Body params:
        company_name   (str, required)
        website        (str, optional)
        anthropic_key  (str, optional) — override de la key del .env
        async_fetch    (bool, optional)
        region         (str, optional, default "es-es")
        pdf            (file, optional)
    """
    # Soporta JSON o form-data
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()

    company_name = (data.get("company_name") or "").strip()
    if not company_name:
        return jsonify({"error": "company_name es obligatorio"}), 400

    website       = (data.get("website") or "").strip() or None
    anthropic_key = (data.get("anthropic_key") or "").strip()
    model         = (data.get("model") or "").strip() or None
    async_fetch   = str(data.get("async_fetch", "false")).lower() == "true"
    region        = data.get("region", "es-es")

    # PDF upload
    pdf_path: Optional[str] = None
    if "pdf" in request.files:
        f = request.files["pdf"]
        if f.filename:
            safe_name = f"{uuid.uuid4().hex}_{f.filename}"
            pdf_path  = str(UPLOAD_DIR / safe_name)
            f.save(pdf_path)

    task_id = uuid.uuid4().hex
    q: queue.Queue = queue.Queue()

    _tasks[task_id] = {"queue": q, "status": "running", "result": None}

    def run_research():
        try:
            system = ResearchSystem(
                region=region,
                async_fetch=async_fetch,
                anthropic_key=anthropic_key,
                progress_callback=lambda msg: q.put({"type": "log", "text": msg}),
            )
            result = system.research(
                company_name = company_name,
                website      = website,
                pdf_path     = pdf_path,
            )
            _tasks[task_id]["result"] = result
            _tasks[task_id]["status"] = "done"

            # Guarda sesión para el chat
            session_id = task_id
            _sessions[session_id] = {
                "company":     company_name,
                "consolidated": result,
                "history":     [],
                "model":       model,
            }

            # Lee el HTML generado para enviarlo al frontend
            html_path = result.get("_output_paths", {}).get("html", "")
            html_content = ""
            if html_path and Path(html_path).exists():
                html_content = Path(html_path).read_text(encoding="utf-8")

            q.put({
                "type":       "done",
                "session_id": session_id,
                "html":       html_content,
                "llm_summary": result.get("llm_summary", ""),
                "output_paths": result.get("_output_paths", {}),
            })

        except Exception as exc:
            _tasks[task_id]["status"] = "error"
            q.put({"type": "error", "text": str(exc)})
        finally:
            q.put(None)  # Señal de fin de stream

    thread = threading.Thread(target=run_research, daemon=True)
    thread.start()

    return jsonify({"task_id": task_id})


# ──────────────────────────────────────────────────────────────────────────────
# API: SSE stream de progreso
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/stream/<task_id>")
def stream(task_id: str):
    """
    Server-Sent Events: emite mensajes de progreso hasta que el task termina.
    El frontend hace: const es = new EventSource('/api/stream/<task_id>')
    """
    if task_id not in _tasks:
        return jsonify({"error": "Task no encontrado"}), 404

    def generate():
        q = _tasks[task_id]["queue"]
        while True:
            try:
                msg = q.get(timeout=60)  # timeout de seguridad
            except queue.Empty:
                yield "data: {\"type\": \"heartbeat\"}\n\n"
                continue

            if msg is None:
                yield "data: {\"type\": \"end\"}\n\n"
                break

            yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# API: Chat con Claude sobre los resultados
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Responde preguntas sobre la investigación usando Claude.

    Body JSON:
        session_id    (str, required)
        question      (str, required)
        anthropic_key (str, optional)
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON requerido"}), 400

    session_id    = data.get("session_id", "")
    question      = (data.get("question") or "").strip()
    anthropic_key = (data.get("anthropic_key") or "").strip()
    model         = (data.get("model") or "").strip() or None

    if not question:
        return jsonify({"error": "question no puede estar vacío"}), 400

    if session_id not in _sessions:
        return jsonify({"error": "Sesión no encontrada. Lanza una investigación primero."}), 404

    session = _sessions[session_id]
    llm = LLMSynthesizer(api_key=anthropic_key or os.getenv("ANTHROPIC_API_KEY", ""))

    answer = llm.chat(
        question             = question,
        company_name         = session["company"],
        consolidated         = session["consolidated"],
        conversation_history = session["history"],
        model                = model or session.get("model"),
    )

    # Actualiza historial
    session["history"].append({"role": "user",      "content": question})
    session["history"].append({"role": "assistant",  "content": answer})

    return jsonify({"answer": answer})


# ──────────────────────────────────────────────────────────────────────────────
# API: Descargar archivos generados
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/download/<path:filename>")
def download(filename: str):
    """Descarga un archivo del directorio output/."""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists() or not file_path.is_relative_to(OUTPUT_DIR):
        return jsonify({"error": "Archivo no encontrado"}), 404
    return send_file(file_path, as_attachment=True)


@app.route("/api/outputs")
def list_outputs():
    """Lista todos los archivos generados en output/."""
    files = [
        {"name": f.name, "size": f.stat().st_size, "url": f"/api/download/{f.name}"}
        for f in sorted(OUTPUT_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
        if f.is_file() and f.name != ".gitkeep"
    ]
    return jsonify(files)


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{'='*50}")
    print(f"  Research System — Web UI")
    print(f"  http://{FLASK_HOST}:{FLASK_PORT}")
    print(f"{'='*50}\n")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG, threaded=True)
