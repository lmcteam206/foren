import os
import sqlite3
from datetime import datetime
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QListWidgetItem, QTextBrowser, QLabel, QFileDialog, 
                             QPushButton, QSplitter, QWidget)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class WhatsAppViewerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Forensic WhatsApp Database Parser")
        self.resize(900, 600)
        self.setStyleSheet("""
            QDialog { background-color: #121b22; color: #e9edef; }
            QLabel { color: #e9edef; font-weight: bold; }
            QListWidget { 
                background-color: #111b21; 
                border: 1px solid #222d34; 
                border-radius: 6px; 
                color: #e9edef;
            }
            QListWidget::item { 
                padding: 12px; 
                border-bottom: 1px solid #222d34; 
            }
            QListWidget::item:selected { 
                background-color: #2a3942; 
                color: #00a884; 
            }
            QTextBrowser { 
                background-color: #0b141a; 
                border: 1px solid #222d34; 
                border-radius: 6px; 
                color: #e9edef;
            }
            QPushButton {
                background-color: #00a884; 
                color: #ffffff; 
                font-weight: bold; 
                border: none; 
                border-radius: 4px; 
                padding: 8px 16px;
            }
            QPushButton:hover { background-color: #006653; }
        """)

        self.db_conn = None
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Top Control Bar
        top_bar = QHBoxLayout()
        self.btn_load = QPushButton("Open WhatsApp Database (.db / .sqlite)")
        self.btn_load.clicked.connect(self.load_database)
        self.lbl_status = QLabel("No file loaded.")
        top_bar.addWidget(self.btn_load)
        top_bar.addWidget(self.lbl_status)
        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        # Splitter for Contacts list (Left) and Chat View (Right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Column: Chat Threads / Contacts
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Chat Threads"))
        self.list_chats = QListWidget()
        self.list_chats.itemClicked.connect(self.display_chat_history)
        left_layout.addWidget(self.list_chats)
        splitter.addWidget(left_widget)

        # Right Column: Chat History Window
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Conversation View"))
        self.chat_display = QTextBrowser()
        right_layout.addWidget(self.chat_display)
        splitter.addWidget(right_widget)

        # Set stretch factors (Left panel 30%, Right panel 70%)
        splitter.setSizes([270, 630])
        main_layout.addWidget(splitter)

    def load_database(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open WhatsApp Database", "", "Database Files (*.db *.sqlite);;All Files (*)")
        if not file_path:
            return

        try:
            self.db_conn = sqlite3.connect(file_path)
            cursor = self.db_conn.cursor()
            
            # Query standard WhatsApp tables schema to see rows available
            # Note: Android schema uses 'jid' or 'chat' tables, sorting conversations
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            self.list_chats.clear()
            self.chat_display.clear()

            # Forensic Parsing Hook for Android/iOS variations
            if "chat" in tables and "message" in tables: # Modern Android Schema
                self.parse_android_schema(cursor)
            elif "ZWACHATSESSION" in tables: # iOS Schema
                self.parse_ios_schema(cursor)
            else:
                # Generic fallback if schemas differ
                self.lbl_status.setText("Unknown database layout structure.")
                return

            self.lbl_status.setText(f"Successfully loaded: {os.path.basename(file_path)}")
        except Exception as e:
            self.lbl_status.setText(f"Error loading database: {str(e)}")

    def parse_android_schema(self, cursor):
        # Fetches conversation strings and maps internally
        cursor.execute("""
            SELECT chat._id, chat.jid_row_id, jid.user 
            FROM chat 
            JOIN jid ON chat.jid_row_id = jid._id 
            WHERE chat.message_count > 0
        """)
        for row in cursor.fetchall():
            chat_id, jid_id, phone_number = row
            item = QListWidgetItem(f"📱 {phone_number if phone_number else 'Group/System'}")
            item.setData(Qt.ItemData.UserRole, {"type": "android", "chat_id": chat_id})
            self.list_chats.addItem(item)

    def parse_ios_schema(self, cursor):
        cursor.execute("SELECT Z_PK, ZCONTACTJID, ZPARTNERNAME FROM ZWACHATSESSION")
        for row in cursor.fetchall():
            pk, jid, name = row
            display_name = name if name else jid.split('@')[0]
            item = QListWidgetItem(f"📱 {display_name}")
            item.setData(Qt.ItemData.UserRole, {"type": "ios", "pk": pk})
            self.list_chats.addItem(item)

    def display_chat_history(self, item):
        data = item.data(Qt.ItemData.UserRole)
        if not data or not self.db_conn:
            return

        cursor = self.db_conn.cursor()
        html_content = """
        <style>
            body { font-family: 'Segoe UI', Helvetica, Arial; padding: 10px; background-color: #0b141a; }
            .msg-container { margin-bottom: 12px; clear: both; overflow: auto; }
            .bubble { padding: 8px 12px; border-radius: 7px; max-width: 75%; display: inline-block; word-wrap: break-word; }
            .incoming { background-color: #202c33; color: #e9edef; float: left; text-align: left; }
            .outgoing { background-color: #005c4b; color: #e9edef; float: right; text-align: right; }
            .meta { font-size: 10px; color: #8696a0; margin-top: 4px; display: block; }
        </style>
        """

        if data["type"] == "android":
            cursor.execute("""
                SELECT from_me, text_data, timestamp 
                FROM message 
                WHERE chat_row_id = ? AND text_data IS NOT NULL
                ORDER BY timestamp ASC
            """, (data["chat_id"],))
            
            for row in cursor.fetchall():
                from_me, text, timestamp = row
                msg_class = "outgoing" if from_me == 1 else "incoming"
                
                # Format epoch timestamp nicely
                time_str = ""
                if timestamp:
                    try:
                        time_str = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M')
                    except Exception:
                        pass

                html_content += f"""
                <div class="msg-container">
                    <div class="bubble {msg_class}">
                        {text}
                        <span class="meta">{time_str}</span>
                    </div>
                </div>
                """

        elif data["type"] == "ios":
            cursor.execute("""
                SELECT ZFROM_ME, ZTEXT, ZMESSAGEDATE 
                FROM ZWAMESSAGE 
                WHERE ZCHATSESSION = ? AND ZTEXT IS NOT NULL
                ORDER BY ZMESSAGEDATE ASC
            """, (data["pk"],))
            
            for row in cursor.fetchall():
                from_me, text, apple_time = row
                msg_class = "outgoing" if from_me == 1 else "incoming"
                
                # iOS references timestamps from 2001-01-01 instead of 1970 standard epoch
                time_str = ""
                if apple_time:
                    try:
                        time_str = datetime.fromtimestamp(apple_time + 978307200).strftime('%Y-%m-%d %H:%M')
                    except Exception:
                        pass

                html_content += f"""
                <div class="msg-container">
                    <div class="bubble {msg_class}">
                        {text}
                        <span class="meta">{time_str}</span>
                    </div>
                </div>
                """

        self.chat_display.setHtml(html_content)

def main_run(main_window_instance):
    """Core entry dynamic hook required by your load_enabled_plugins structural logic."""
    dialog = WhatsAppViewerDialog(main_window_instance)
    dialog.exec()