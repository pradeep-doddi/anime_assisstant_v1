import sys
import os
import json
import threading
import requests
def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit,
    QTextEdit, QPushButton
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, pyqtSignal, QPoint

# ---------------- CONFIG ----------------
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"   # must exist in `ollama list`
SUMMARY_CHARS = 280
SHORT_MEMORY_LIMIT = 4

PROFILE_FILE = "profile.json"
SHORT_MEMORY_FILE = "short_memory.json"
POSITION_FILE = "position.json"
# ---------------------------------------


# ---------- Full Answer Window ----------
class FullAnswerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Assistant – Full Answer")
        self.resize(600, 500)

        self.text = QTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setGeometry(10, 10, 580, 480)

    def set_text(self, text):
        self.text.setPlainText(text)


# ---------- Main Assistant ----------
class Assistant(QWidget):
    answer_ready = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.drag_position = None

        # ---------- Window ----------
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # ---------- Image ----------
        pixmap = QPixmap(resource_path("img1.png"))

        pixmap = pixmap.scaled( 
            pixmap.width() // 2,
            pixmap.height() // 2,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.image = QLabel(self)
        self.image.setPixmap(pixmap)
        self.image.move(0, 220)

        self.resize(pixmap.width(), pixmap.height() + 220)

        # ---------- Position ----------
        saved = self.load_position()
        if saved:
            self.move(saved)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(
                screen.width() - self.width() - 15,
                screen.height() - self.height() - 15
            )

        # ---------- Bubble ----------
        self.output = QTextEdit(self)
        self.output.setReadOnly(True)
        self.output.setGeometry(10, 10, self.width() - 20, 160)
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

        # ---------- Expand ----------
        self.expand_btn = QPushButton("View full answer", self)
        self.expand_btn.setGeometry(10, 175, 140, 22)
        self.expand_btn.clicked.connect(self.show_full_answer)
        self.expand_btn.hide()

        # ---------- Input ----------
        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Ask me anything…")
        self.input.setGeometry(10, 200, self.width() - 20, 30)
        self.input.returnPressed.connect(self.on_enter)
        self.input.hide()

        # ---------- Memory ----------
        self.profile = self.load_json(PROFILE_FILE, {})
        self.short_memory = self.load_json(SHORT_MEMORY_FILE, [])
        self.full_answer_text = ""

        self.full_window = FullAnswerWindow()
        self.answer_ready.connect(self.render_answer)

    # ---------- File helpers ----------
    def load_json(self, file, default):
        if os.path.exists(file):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return default

    def save_json(self, file, data):
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_position(self):
        if os.path.exists(POSITION_FILE):
            try:
                with open(POSITION_FILE, "r") as f:
                    d = json.load(f)
                    return QPoint(d["x"], d["y"])
            except:
                pass
        return None

    def save_position(self):
        p = self.pos()
        with open(POSITION_FILE, "w") as f:
            json.dump({"x": p.x(), "y": p.y()}, f)

    # ---------- Mouse (Shift + drag) ----------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.modifiers() == Qt.ShiftModifier:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        else:
            self.input.clear()
            self.input.show()
            self.input.setFocus()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and event.modifiers() == Qt.ShiftModifier:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.save_position()

    # ---------- Input ----------
    def on_enter(self):
        text = self.input.text().strip()
        if not text:
            return

        text_lower = text.lower()

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
        self.output.setText("Thinking…")
        self.output.show()
        self.expand_btn.hide()

        threading.Thread(
            target=self.ask_ollama,
            args=(text,),
            daemon=True
        ).start()

    # ---------- Ollama ----------
    def ask_ollama(self, user_text):
        try:
            context = []

            if "name" in self.profile:
                context.append(f"The user's name is {self.profile['name']}.")

            for m in self.short_memory:
                context.append(f"Previously discussed: {m['user']}.")

            prompt = f"""
You are a helpful desktop assistant.

Context:
{chr(10).join(context)}

Question:
{user_text}

Answer clearly.
""".strip()

            r = requests.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
                timeout=120
            )

            answer = (r.json().get("response") or "").strip()
            if not answer:
                answer = "⚠️ No response from model."

            self.short_memory.append({"user": user_text, "assistant": answer})
            self.short_memory = self.short_memory[-SHORT_MEMORY_LIMIT:]
            self.save_json(SHORT_MEMORY_FILE, self.short_memory)

        except Exception as e:
            answer = f"Error: {e}"

        self.answer_ready.emit(answer)

    # ---------- Render ----------
    def render_answer(self, text):
        self.full_answer_text = text

        if len(text) > SUMMARY_CHARS:
            summary = text[:SUMMARY_CHARS].rsplit(" ", 1)[0] + "…\n\n[View full answer]"
            self.expand_btn.show()
        else:
            summary = text
            self.expand_btn.hide()

        self.output.setPlainText(summary)
        self.input.clear()
        self.input.show()
        self.input.setFocus()

    def show_full_answer(self):
        self.full_window.set_text(self.full_answer_text)
        self.full_window.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Assistant()
    w.show()
    sys.exit(app.exec_())
