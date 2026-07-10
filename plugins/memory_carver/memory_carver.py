import os
import re
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
                             QTextBrowser, QLabel, QFileDialog, QPushButton, QSplitter, QWidget)
from PyQt6.QtCore import Qt

class MemoryCarverDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Volatile Memory Data Carver & Minidump Triage")
        self.resize(1000, 650)
        self.setStyleSheet("""
            QDialog { background-color: #121212; color: #ffffff; }
            QLabel { color: #ffffff; font-weight: bold; }
            QListWidget { background-color: #1e1e1e; border: 1px solid #333333; color: #ffffff; border-radius: 4px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #2a2a2a; }
            QListWidget::item:selected { background-color: #d9534f; color: white; }
            QTextBrowser { background-color: #0d0d0d; border: 1px solid #333333; color: #00ff00; font-family: 'Consolas', 'Courier New'; }
            QPushButton { background-color: #d9534f; color: white; font-weight: bold; border-radius: 4px; padding: 8px 16px; }
            QPushButton:hover { background-color: #c9302c; }
        """)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Control panel bar
        top_bar = QHBoxLayout()
        self.btn_browse = QPushButton("📁 Open Custom Dump File (.dmp / .raw)")
        self.btn_browse.clicked.connect(self.browse_dump_file)
        
        self.btn_minidump = QPushButton("⚡ Auto-Scan Local Windows Minidumps")
        self.btn_minidump.clicked.connect(self.scan_local_minidumps)
        
        self.lbl_status = QLabel("Load a memory structure to begin block triage.")
        top_bar.addWidget(self.btn_browse)
        top_bar.addWidget(self.btn_minidump)
        top_bar.addWidget(self.lbl_status)
        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        # Splitter window
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Column: Discovered Artifact Entries
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Extracted Volatile Strings (Click to View)"))
        self.list_strings = QListWidget()
        self.list_strings.itemClicked.connect(self.display_string_block)
        left_layout.addWidget(self.list_strings)
        splitter.addWidget(left_widget)

        # Right Column: Payload Inspection Browser
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Raw Text Buffer Segment"))
        self.text_display = QTextBrowser()
        right_layout.addWidget(self.text_display)
        splitter.addWidget(right_widget)

        splitter.setSizes([350, 650])
        main_layout.addWidget(splitter)

    def browse_dump_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Volatile Dump File", "", "Memory Dumps (*.dmp *.raw *.mem *.bin);;All Files (*)"
        )
        if file_path:
            self.carve_memory_file(file_path)

    def scan_local_minidumps(self):
        """Locates Windows system crash dumps without altering target file system permissions."""
        minidump_dir = r"C:\Windows\Minidump"
        if not os.path.exists(minidump_dir):
            self.lbl_status.setText("No local Minidump directory detected on this operating system.")
            return

        try:
            files = [os.path.join(minidump_dir, f) for f in os.listdir(minidump_dir) if f.lower().endswith('.dmp')]
            if not files:
                self.lbl_status.setText("Minidump folder structure found, but no active records exist.")
                return
            
            # Target the most recent crash file dropped by the operating system kernel
            latest_file = max(files, key=os.path.getmtime)
            self.carve_memory_file(latest_file)
            
        except PermissionError:
            self.lbl_status.setText("⚠ Access Denied: Please restart the main framework as an Administrator.")
        except Exception as e:
            self.lbl_status.setText(f"System access dropped: {str(e)}")

    def carve_memory_file(self, path):
        self.list_strings.clear()
        self.text_display.clear()
        self.lbl_status.setText("Carving binary blocks... please wait...")
        self.repaint()

        try:
            with open(path, "rb") as f:
                # Read chunks to manage memory footprint safely if checking huge files
                binary_data = f.read(50 * 1024 * 1024) # Cap triage scan to first 50MB for instant parsing

            # 1. Regex Pattern for standard ASCII strings (Length 8+)
            ascii_pattern = rb"[a-zA-Z0-9\/\\:._\-?&=]{8,}"
            ascii_matches = re.findall(ascii_pattern, binary_data)

            # 2. Regex Pattern for Windows UTF-16 Little-Endian strings (Wide strings used heavily by Tor/OS)
            utf16_pattern = rb"(?:[a-zA-Z0-9\/\\:._\-?&=]\x00){8,}"
            utf16_matches = re.findall(utf16_pattern, binary_data)

            extracted_count = 0
            
            # Process ASCII strings
            for match in ascii_matches[:1000]: # Cap item entries to prevent interface UI lag
                decoded = match.decode('ascii', errors='ignore').strip()
                if decoded.startswith(("http", "onion", "C:", "User", "select", "password")):
                    item = QListWidgetItem(f"🔤 [ASCII] - {decoded[:40]}...")
                    item.setData(Qt.ItemDataRole.UserRole, decoded)
                    self.list_strings.addItem(item)
                    extracted_count += 1

            # Process UTF-16 strings
            for match in utf16_matches[:1000]:
                decoded = match.decode('utf-16le', errors='ignore').strip()
                if len(decoded) >= 8:
                    item = QListWidgetItem(f"🔤 [UTF-16 Wide] - {decoded[:40]}...")
                    item.setData(Qt.ItemDataRole.UserRole, decoded)
                    self.list_strings.addItem(item)
                    extracted_count += 1

            self.lbl_status.setText(f"File Triage Complete: {os.path.basename(path)} ({extracted_count} high-interest tracks isolated).")

        except Exception as e:
            self.lbl_status.setText(f"Failed parsing memory blocks: {str(e)}")

    def display_string_block(self, item):
        raw_text = item.data(Qt.ItemDataRole.UserRole)
        self.text_display.setPlainText(raw_text)

def main_run(main_window_instance):
    dialog = MemoryCarverDialog(main_window_instance)
    dialog.exec()