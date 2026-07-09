import os
import sqlite3
import struct
from datetime import datetime
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QListWidgetItem, QTextBrowser, QLabel, QFileDialog, 
                             QPushButton, QSplitter, QWidget, QInputDialog, QMessageBox)
from PyQt6.QtCore import Qt
from Crypto.Cipher import AES

class WhatsAppViewerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Forensic WhatsApp Database Parser & Decrypter")
        self.resize(950, 650)
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
        self.decrypted_temp_path = None
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        self.btn_load = QPushButton("Open Database (.db / .crypt14 / .crypt15)")
        self.btn_load.clicked.connect(self.load_database)
        self.lbl_status = QLabel("No file loaded.")
        top_bar.addWidget(self.btn_load)
        top_bar.addWidget(self.lbl_status)
        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Chat Threads"))
        self.list_chats = QListWidget()
        self.list_chats.itemClicked.connect(self.display_chat_history)
        left_layout.addWidget(self.list_chats)
        splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Conversation View"))
        self.chat_display = QTextBrowser()
        right_layout.addWidget(self.chat_display)
        splitter.addWidget(right_widget)

        splitter.setSizes([270, 630])
        main_layout.addWidget(splitter)

    def load_database(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open WhatsApp Database", "", 
            "All Allowed Files (*.db *.sqlite *.crypt14 *.crypt15);;Encrypted Backups (*.crypt14 *.crypt15);;Standard SQLite (*.db *.sqlite)"
        )
        if not file_path:
            return

        target_path = file_path

        # Check if the file is encrypted with crypt14 or crypt15
        if file_path.endswith(('.crypt14', '.crypt15')):
            hex_key, ok = QInputDialog.getText(
                self, "Decryption Key Required", 
                "Enter 64-character Hex Encryption Key or path to key file:"
            )
            if not ok or not hex_key.strip():
                return
            
            decrypted_path = file_path + ".decrypted.db"
            if self.decrypt_backup(file_path, decrypted_path, hex_key.strip()):
                target_path = decrypted_path
                self.decrypted_temp_path = decrypted_path
            else:
                return

        try:
            self.db_conn = sqlite3.connect(target_path)
            cursor = self.db_conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            self.list_chats.clear()
            self.chat_display.clear()

            if "chat" in tables and "message" in tables:
                self.parse_android_schema(cursor)
            elif "ZWACHATSESSION" in tables:
                self.parse_ios_schema(cursor)
            else:
                self.lbl_status.setText("Unknown structural database layout.")
                return

            self.lbl_status.setText(f"Loaded: {os.path.basename(file_path)}")
        except Exception as e:
            self.lbl_status.setText(f"Error reading database: {str(e)}")

    def decrypt_backup(self, enc_path, out_path, key_input):
        """ Handles forensic parsing and decryption arrays for Crypt14 and Crypt15 layers. """
        try:
            # 1. Resolve key raw string to byte sequence
            if len(key_input) == 64:
                key_bytes = bytes.fromhex(key_input)
            elif os.path.exists(key_input):
                with open(key_input, 'rb') as f:
                    # Quick skip layout headers if standard Android key asset container
                    f.seek(11)
                    key_bytes = f.read(32)
            else:
                QMessageBox.critical(self, "Decryption Error", "Invalid Hex Key length or Key File path.")
                return False

            with open(enc_path, 'rb') as f:
                data = f.read()

            # 2. Extract initialization vector offsets and data blocks based on header types
            if enc_path.endswith('.crypt15'):
                # Crypt15 processing parameters
                iv = data[0:12]
                encrypted_payload = data[12:]
                cipher = AES.new(key_bytes, AES.MODE_GCM, nonce=iv)
                decrypted_data = cipher.decrypt(encrypted_payload)
            else:
                # Crypt14 fallback processing parameters
                iv = data[51:67]
                encrypted_payload = data[67:]
                cipher = AES.new(key_bytes, AES.MODE_CBC, iv=iv)
                decrypted_data = cipher.decrypt(encrypted_payload)

            # Strip possible padding or check SQLite raw magic header bytes
            if not decrypted_data.startswith(b"SQLite format 3"):
                # Try offset adjustments if wrapper parameters are offset
                header_index = decrypted_data.find(b"SQLite format 3")
                if header_index != -1:
                    decrypted_data = decrypted_data[header_index:]
                else:
                    QMessageBox.critical(self, "Decryption Error", "Decryption failed. Invalid key or corrupted header sequence.")
                    return False

            with open(out_path, 'wb') as f:
                f.write(decrypted_data)
            return True

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Decryption exception error: {str(e)}")
            return False

    def parse_android_schema(self, cursor):
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

    def closeEvent(self, event):
        """ Automatically wipe out temporary forensic decrypted database assets on window exit. """
        if self.db_conn:
            self.db_conn.close()
        if self.decrypted_temp_path and os.path.exists(self.decrypted_temp_path):
            try:
                os.remove(self.decrypted_temp_path)
            except Exception:
                pass
        event.accept()

def main_run(main_window_instance):
    dialog = WhatsAppViewerDialog(main_window_instance)
    dialog.exec()