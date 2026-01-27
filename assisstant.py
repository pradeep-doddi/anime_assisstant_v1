import sys
import os
import json
import threading

from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QLineEdit
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, pyqtSignal

MEMORY_FILE = "memory.json"
MAX_CHARS = 400


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
        self.image.move(0, 140)

        self.resize(pixmap.width(), pixmap.height() + 140)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.width() - self.width() - 15,
            screen.height() - self.height() - 15
        )

        # ---------- Output bubble ----------
        self.output = QLabel(self)
        self.output.setWordWrap(True)
        self.output.setGeometry(10, 10, self.width() - 20, 110)
        self.output.setStyleSheet("""
            QLabel {
                background-color: rgba(0,0,0,210);
                color: white;
                padding: 8px;
                border-radius: 10px;
                font-size: 11px;
            }
        """)
        self.output.hide()

        # ---------- Input ----------
        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Ask me anything…")
        self.input.setGeometry(10, 120, self.width() - 20, 30)
        self.input.returnPressed.connect(self.on_enter)
        self.input.hide()

        # ---------- Gemini ----------
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel("models/gemini-flash-latest")

        # ---------- Memory ----------
        self.memory = []

        self.answer_ready.connect(self.render_answer)

    # ---------- Click ----------
    def mousePressEvent(self, e):
        self.input.clear()
        self.input.show()
        self.input.setFocus()

    # ---------- Enter ----------
    def on_enter(self):
        text = self.input.text().strip()
        if not text:
            return

        self.input.hide()
        self.output.setText("Thinking…")
        self.output.show()

        threading.Thread(
            target=self.ask_gemini,
            args=(text,),
            daemon=True
        ).start()

    # ---------- Gemini ----------
    def ask_gemini(self, user_text):
        try:
            chat = self.model.start_chat()

            # minimal safe memory
            for m in self.memory[-1:]:
                chat.send_message(m["user"])
                chat.send_message(m["assistant"])

            response = chat.send_message(user_text)
            answer = response.text.strip() if response.text else ""

            if not answer:
                answer = "I didn’t receive a reply. Please try again."

            answer = answer[:MAX_CHARS]

            self.memory.append({
                "user": user_text,
                "assistant": answer
            })

        except Exception as e:
            msg = str(e).lower()
            if "quota" in msg or "limit" in msg:
                answer = "Usage limit reached. Please wait and try again."
            else:
                answer = f"Error: {e}"

        self.answer_ready.emit(answer)

    # ---------- Render ----------
    def render_answer(self, text):
        self.output.setText(text)
        self.input.clear()
        self.input.show()
        self.input.setFocus()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Assistant()
    w.show()
    sys.exit(app.exec_())
