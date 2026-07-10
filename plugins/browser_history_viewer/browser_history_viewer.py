import os
import sys
import sqlite3
import shutil
import struct
import re
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QLabel, QPushButton, QHeaderView, QTabWidget)
from PyQt6.QtCore import Qt

# Match the appdata layout tracking you introduced in main.py
APPDATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ForensicWorkspace")
TEMP_EXTRACT_DIR = os.path.join(APPDATA_DIR, "temp_browser_data")

class BrowserHistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Multi-Browser History & Session Carver")
        self.resize(1100, 650)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #ffffff; }
            QLabel { color: #ffffff; font-weight: bold; }
            QTableWidget { 
                background-color: #252526; border: 1px solid #3c3c3c; 
                color: #ffffff; gridline-color: #3c3c3c; 
            }
            QTableWidget::item { padding: 5px; }
            QHeaderView::section { background-color: #2d2d2d; color: white; padding: 4px; border: 1px solid #3c3c3c; }
            QPushButton { background-color: #007acc; color: white; border-radius: 4px; padding: 8px 15px; font-weight: bold; }
            QPushButton:hover { background-color: #0062a3; }
            QTabWidget::pane { border: 1px solid #3c3c3c; background: #252526; }
            QTabBar::tab { background: #2d2d2d; color: #aaaaaa; padding: 8px 15px; }
            QTabBar::tab:selected { background: #252526; color: white; font-weight: bold; }
        """)
        
        os.makedirs(TEMP_EXTRACT_DIR, exist_ok=True)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Control Header
        ctrl_layout = QHBoxLayout()
        self.btn_scan = QPushButton("🔍 Scan System Browsers")
        self.btn_scan.clicked.connect(self.execute_system_scan)
        self.lbl_status = QLabel("Ready to analyze paths.")
        ctrl_layout.addWidget(self.btn_scan)
        ctrl_layout.addWidget(self.lbl_status)
        ctrl_layout.addStretch()
        main_layout.addLayout(ctrl_layout)
        
        # Tabs for layouts
        self.tabs = QTabWidget()
        
        # Tab 1: Live Databases
        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(["Timestamp", "Browser", "Title", "URL"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.history_table, "Active Database Logs")
        
        # Tab 2: Carved / Wiped Sessions
        self.deleted_table = QTableWidget(0, 3)
        self.deleted_table.setHorizontalHeaderLabels(["Source File Context", "Potential Recovered URL", "Metadata Info"])
        self.deleted_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.deleted_table.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.deleted_table, "⚠ Carved Sessions (Wiped History Backups)")
        
        main_layout.addWidget(self.tabs)

    def convert_webkit_time(self, timestamp):
        """Converts Chromium WebKit microsecond offsets since 1601 to readable layout."""
        if not timestamp:
            return "N/A"
        try:
            epoch_start = datetime(1601, 1, 1)
            delta = timedelta(microseconds=timestamp)
            return (epoch_start + delta).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return str(timestamp)

    def get_browser_paths(self):
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        return {
            "Google Chrome": {
                "history": os.path.join(local_appdata, r"Google\Chrome\User Data\Default\History"),
                "sessions": os.path.join(local_appdata, r"Google\Chrome\User Data\Default\Sessions")
            },
            "Microsoft Edge": {
                "history": os.path.join(local_appdata, r"Microsoft\Edge\User Data\Default\History"),
                "sessions": os.path.join(local_appdata, r"Microsoft\Edge\User Data\Default\Sessions")
            },
            "Brave Browser": {
                "history": os.path.join(local_appdata, r"BraveSoftware\Brave-Browser\User Data\Default\History"),
                "sessions": os.path.join(local_appdata, r"BraveSoftware\Brave-Browser\User Data\Default\Sessions")
            }
        }

    def execute_system_scan(self):
        self.history_table.setRowCount(0)
        self.deleted_table.setRowCount(0)
        paths = self.get_browser_paths()
        
        active_records = 0
        carved_records = 0
        
        for browser_name, target_paths in paths.items():
            # 1. Parse active live log files
            if os.path.exists(target_paths["history"]):
                temp_copy = os.path.join(TEMP_EXTRACT_DIR, f"{browser_name}_History")
                try:
                    shutil.copy2(target_paths["history"], temp_copy)
                    records = self.parse_history_db(temp_copy, browser_name)
                    active_records += len(records)
                except Exception as e:
                    print(f"[-] Safe backup allocation bypassed for {browser_name}: {str(e)}")

            # 2. Carve deleted records out of unpurged session SNSS files
            if os.path.exists(target_paths["sessions"]):
                try:
                    for file in os.listdir(target_paths["sessions"]):
                        if file.startswith(("Session_", "Tabs_")):
                            full_path = os.path.join(target_paths["sessions"], file)
                            urls_carved = self.carve_snss_session_file(full_path)
                            for url in urls_carved:
                                row = self.deleted_table.rowCount()
                                self.deleted_table.insertRow(row)
                                self.deleted_table.setItem(row, 0, QTableWidgetItem(f"{browser_name} ({file})"))
                                self.deleted_table.setItem(row, 1, QTableWidgetItem(url))
                                self.deleted_table.setItem(row, 2, QTableWidgetItem("Persistent Open Session Segment"))
                                carved_records += 1
                except Exception as e:
                    print(f"[-] Session parsing failed for {browser_name}: {str(e)}")
                    
        self.history_table.sortItems(0, Qt.SortOrder.DescendingOrder)
        self.lbl_status.setText(f"Analysis Complete. Found {active_records} active entries and {carved_records} carved session artifacts.")

    def parse_history_db(self, db_path, browser_name):
        entries = []
        try:
            # Query strings using standard implicit table relationships
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT visits.visit_time, urls.title, urls.url 
                FROM urls, visits 
                WHERE urls.id = visits.url 
                ORDER BY visits.visit_time DESC
            """)
            
            for row in cursor.fetchall():
                v_time, title, url = row
                readable_time = self.convert_webkit_time(v_time)
                
                row_idx = self.history_table.rowCount()
                self.history_table.insertRow(row_idx)
                self.history_table.setItem(row_idx, 0, QTableWidgetItem(readable_time))
                self.history_table.setItem(row_idx, 1, QTableWidgetItem(browser_name))
                self.history_table.setItem(row_idx, 2, QTableWidgetItem(title if title else "[No Title Passed]"))
                self.history_table.setItem(row_idx, 3, QTableWidgetItem(url))
                entries.append(url)
            conn.close()
        except Exception as e:
            print(f"[-] SQLite execution skipped on path index: {str(e)}")
        return entries

    def carve_snss_session_file(self, file_path):
        """Extracts ASCII/UTF-8 URL signatures directly from raw binary blocks."""
        found_urls = set()
        try:
            with open(file_path, "rb") as f:
                raw_bytes = f.read()
                
            # Basic regex scanning string sequences inside raw blocks for tracking protocols
            url_pattern = b"https?://[a-zA-Z0-9./?=&_,-]+"
            matches = re.findall(url_pattern, raw_bytes)
            for match in matches:
                url_str = match.decode('utf-8', errors='ignore')
                # Exclude basic internal extension updates or standard configurations
                if "newtab" not in url_str and "chrome-extension" not in url_str:
                    found_urls.add(url_str)
        except Exception:
            pass
        return list(found_urls)

    def closeEvent(self, event):
        """Cleanup temporary shadow copies on window exit."""
        if os.path.exists(TEMP_EXTRACT_DIR):
            try:
                shutil.rmtree(TEMP_EXTRACT_DIR)
            except Exception:
                pass
        event.accept()

def main_run(main_window_instance):
    dialog = BrowserHistoryDialog(main_window_instance)
    dialog.exec()