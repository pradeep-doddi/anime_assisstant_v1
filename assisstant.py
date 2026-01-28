import sys
import os
import json
import threading
import requests

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QTextEdit
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, pyqtSignal

# ---------------- CONFIG ----------------
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"   # must be pulled
MAX_CHARS = 450
SHORT_MEMORY_LIMIT = 4

PROFILE_FILE = "profile.json"
SHORT_MEMORY_FILE = "short_memory.json"
# ----------------------------------------


class Assistant(QWidget):
    answer_ready = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        # ---------- Window ----------
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # ---------- Image ----------
        pixmap = QPixmap("img1.png")
        pixmap = pixmap.scaled(
            pixmap.width() // 2,
            pixmap.height() // 2,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.image = QLabel(self)
        self.image.setPixmap(pixmap)
        self.image.move(0, 210)

        self.resize(pixmap.width(), pixmap.height() + 210)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.width() - self.width() - 15,
            screen.height() - self.height() - 15
        )

        # ---------- Output (Scrollable Floating Bubble) ----------
        self.output = QTextEdit(self)
        self.output.setReadOnly(True)
        self.output.setGeometry(10, 10, self.width() - 20, 180)
        self.output.setStyleSheet("""
            QTextEdit {
                background-color: rgba(0,0,0,210);
                color: white;
                padding: 8px;
                border-radius: 12px;
                font-size: 11px;
            }
        """)
        self.output.hide()

        # ---------- Input ----------
        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Ask me anything…")
        self.input.setGeometry(10, 195, self.width() - 20, 30)
        self.input.returnPressed.connect(self.on_enter)
        self.input.hide()

        self.answer_ready.connect(self.render_answer)

        # ---------- Memory ----------
        self.profile = self.load_json(PROFILE_FILE, {})
        self.short_memory = self.load_json(SHORT_MEMORY_FILE, [])

    # ---------- JSON helpers ----------
    def load_json(self, file, default):
        if os.path.exists(file):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return default
        return default

    def save_json(self, file, data):
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # ---------- Click ----------
    def mousePressEvent(self, event):
        self.input.clear()
        self.input.show()
        self.input.setFocus()

    # ---------- Enter ----------
    def on_enter(self):
        text = self.input.text().strip()
        if not text:
            return

        text_lower = text.lower()

        # ---- Remember name ----
        if "my name is" in text_lower:
            name = text.split("is")[-1].strip().capitalize()
            self.profile["name"] = name
            self.save_json(PROFILE_FILE, self.profile)
            self.render_answer(f"Got it 👍 I’ll call you {name}.")
            return

        if "what is my name" in text_lower:
            name = self.profile.get("name")
            self.render_answer(
                f"Your name is {name}." if name else "You haven’t told me your name yet."
            )
            return

        self.input.hide()
        self.output.clear()
        self.output.setText("Thinking…")
        self.output.show()

        threading.Thread(
            target=self.ask_ollama,
            args=(text,),
            daemon=True
        ).start()

    # ---------- Ollama ----------
    def ask_ollama(self, user_text):
        try:
            context_lines = []

            if "name" in self.profile:
                context_lines.append(f"The user's name is {self.profile['name']}.")

            for m in self.short_memory:
                context_lines.append(
                    f"Previously discussed: {m['user']}."
                )

            context = "\n".join(context_lines)

            prompt = f"""
You are a helpful desktop assistant.

Context:
{context}

Question:
{user_text}

Answer clearly and concisely.
""".strip()

            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=120
            )

            data = response.json()
            answer = (data.get("response") or "").strip()

            if not answer:
                answer = "⚠️ The model did not return a response. Please rephrase."

            # ---- Safe truncation (no mid-word cut) ----
            if len(answer) > MAX_CHARS:
                answer = answer[:MAX_CHARS].rsplit(" ", 1)[0]
                answer += "\n\n…(response truncated — ask me to continue)"

            # ---- Short memory ----
            self.short_memory.append({
                "user": user_text,
                "assistant": answer
            })
            self.short_memory = self.short_memory[-SHORT_MEMORY_LIMIT:]
            self.save_json(SHORT_MEMORY_FILE, self.short_memory)

        except Exception as e:
            answer = f"Error: {e}"

        self.answer_ready.emit(answer)

    # ---------- Render ----------
    def render_answer(self, text):
        self.output.setPlainText(text)
        self.output.verticalScrollBar().setValue(
            self.output.verticalScrollBar().maximum()
        )
        self.input.clear()
        self.input.show()
        self.input.setFocus()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Assistant()
    w.show()
    sys.exit(app.exec_())
