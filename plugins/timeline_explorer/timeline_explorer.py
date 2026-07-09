import os
import sqlite3
import json
from datetime import datetime
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QListWidgetItem, QTextBrowser, QLabel, QFileDialog, 
                             QPushButton, QSplitter, QWidget)
from PyQt6.QtCore import Qt

class TimelineExplorerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Windows Timeline Database Explorer")
        self.resize(1000, 650)
        self.setStyleSheet("""
            QDialog { background-color: #1a1a1a; color: #ffffff; }
            QLabel { color: #ffffff; font-weight: bold; }
            QListWidget { 
                background-color: #262626; 
                border: 1px solid #333333; 
                border-radius: 6px; 
                color: #ffffff;
            }
            QListWidget::item { 
                padding: 10px; 
                border-bottom: 1px solid #333333; 
            }
            QListWidget::item:selected { 
                background-color: #007acc; 
                color: #ffffff; 
            }
            QTextBrowser { 
                background-color: #111111; 
                border: 1px solid #333333; 
                border-radius: 6px; 
                color: #dddddd;
            }
            QPushButton {
                background-color: #007acc; 
                color: #ffffff; 
                font-weight: bold; 
                border: none; 
                border-radius: 4px; 
                padding: 8px 16px;
            }
            QPushButton:hover { background-color: #005999; }
        """)

        self.db_conn = None
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Top Control Bar
        top_bar = QHBoxLayout()
        self.btn_load = QPushButton("Load ActivitiesCache.db")
        self.btn_load.clicked.connect(self.load_database)
        
        self.btn_auto_locate = QPushButton("Auto-Locate Current User DB")
        self.btn_auto_locate.clicked.connect(self.auto_locate_db)
        
        self.lbl_status = QLabel("No database loaded.")
        
        top_bar.addWidget(self.btn_load)
        top_bar.addWidget(self.btn_auto_locate)
        top_bar.addWidget(self.lbl_status)
        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        # Splitter Layout
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Column: List of logged events
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Activity Events Logs"))
        self.list_events = QListWidget()
        self.list_events.itemClicked.connect(self.display_event_details)
        left_layout.addWidget(self.list_events)
        splitter.addWidget(left_widget)

        # Right Column: Detailed Payload Inspection
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Detailed Inspection Metadata"))
        self.details_display = QTextBrowser()
        right_layout.addWidget(self.details_display)
        splitter.addWidget(right_widget)

        splitter.setSizes([450, 550])
        main_layout.addWidget(splitter)

    def auto_locate_db(self):
        """Attempts to target the live Windows Timeline cache for the logged-in profile."""
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if not local_appdata:
            self.lbl_status.setText("Could not resolve local AppData environment path.")
            return

        # Default path layout for Windows Timeline storage
        timeline_dir = os.path.join(local_appdata, "ConnectedDevicesPlatform")
        
        found_dbs = []
        if os.path.exists(timeline_dir):
            for root, dirs, files in os.walk(timeline_dir):
                if "ActivitiesCache.db" in files:
                    found_dbs.append(os.path.join(root, "ActivitiesCache.db"))

        if found_dbs:
            # Pick the first matching configuration found
            self.process_database_file(found_dbs[0])
        else:
            self.lbl_status.setText("Live ActivitiesCache.db file not detected or locked by system.")

    def load_database(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select ActivitiesCache.db", "", "Database Files (*.db);;All Files (*)"
        )
        if file_path:
            self.process_database_file(file_path)

    def process_database_file(self, path):
        try:
            # Using URI mode allows reading even if Windows currently locks the database file context
            self.db_conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            cursor = self.db_conn.cursor()

            # Execute unified tracking query pulling back executable types, dates, and package fields
            cursor.execute("""
                SELECT AppId, StartTime, EndTime, Payload, ETag 
                FROM Activity 
                WHERE Payload IS NOT NULL 
                ORDER BY StartTime DESC
            """)
            
            self.list_events.clear()
            self.details_display.clear()

            for row in cursor.fetchall():
                app_id_raw, start_time, end_time, payload_raw, etag = row
                
                # Parse readable application names out of JSON or Windows package paths
                app_name = "Unknown App"
                try:
                    app_data = json.loads(app_id_raw) if app_id_raw.startswith('[') or app_id_raw.startswith('{') else app_id_raw
                    if isinstance(app_data, list) and len(app_data) > 0:
                        app_name = app_data[0].get("application", "").split("\\")[-1]
                    else:
                        app_name = str(app_id_raw).split("\\")[-1]
                except Exception:
                    app_name = str(app_id_raw)

                # Format Unix timestamp string offsets
                time_str = "No Time"
                if start_time:
                    try:
                        time_str = datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        time_str = str(start_time)

                # Append visualization entry items
                item = QListWidgetItem(f"🕒 [{time_str}] - {app_name}")
                item.setData(Qt.ItemData.UserRole, {
                    "app_id": app_id_raw,
                    "start": start_time,
                    "end": end_time,
                    "payload": payload_raw
                })
                self.list_events.addItem(item)

            self.lbl_status.setText(f"Active Session: {os.path.basename(path)}")

        except Exception as e:
            self.lbl_status.setText(f"Failed to read file targets: {str(e)}")

    def display_event_details(self, item):
        data = item.data(Qt.ItemData.UserRole)
        if not data:
            return

        # Formatting values nicely
        start_dt = datetime.fromtimestamp(data["start"]).strftime('%Y-%m-%d %H:%M:%S') if data["start"] else "N/A"
        end_dt = datetime.fromtimestamp(data["end"]).strftime('%Y-%m-%d %H:%M:%S') if data["end"] else "N/A"

        # Attempt formatting embedded payload blocks inside activity properties
        formatted_json = ""
        try:
            payload_obj = json.loads(data["payload"])
            formatted_json = json.dumps(payload_obj, indent=4, ensure_ascii=False)
            
            # Extract actionable data strings if they exist inside the standard Windows payload properties
            description = payload_obj.get("description", "None Available")
            display_text = payload_obj.get("displayText", "None Available")
        except Exception:
            formatted_json = str(data["payload"])
            description = "Error Parsing Payload Properties"
            display_text = "N/A"

        html_content = f"""
        <h3>Activity Event Parameters</h3>
        <hr/>
        <b>Application Path Source:</b><br/> {data["app_id"]}<br/><br/>
        <b>Start Time:</b> {start_dt}<br/>
        <b>End Time:</b> {end_dt}<br/><br/>
        <b>Interacted Asset Details:</b> {display_text}<br/>
        <b>Description/URL Tracked:</b> {description}<br/>
        <hr/>
        <h4>Raw JSON Payload Buffer Inspection</h4>
        <pre style="color: #00ff00;">{formatted_json}</pre>
        """
        self.details_display.setHtml(html_content)

def main_run(main_window_instance):
    dialog = TimelineExplorerDialog(main_window_instance)
    dialog.exec()