import os
import re
import shutil
import base64
import subprocess
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QLabel, QPushButton, QHeaderView, QTabWidget)
from PyQt6.QtCore import Qt

APPDATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ForensicWorkspace")
TEMP_EXTRACT_DIR = os.path.join(APPDATA_DIR, "temp_event_data")

class EventLogParserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Windows Event Log Timeline Triage (.evtx)")
        self.resize(1150, 650)
        self.setStyleSheet("""
            QDialog { background-color: #141419; color: #ffffff; }
            QLabel { color: #ffffff; font-weight: bold; }
            QTableWidget { 
                background-color: #1e1e24; border: 1px solid #2d2d3a; 
                color: #ffffff; gridline-color: #2d2d3a; 
            }
            QHeaderView::section { background-color: #2a2a35; color: white; padding: 5px; border: 1px solid #2d2d3a; }
            QPushButton { background-color: #337ab7; color: white; border-radius: 4px; padding: 8px 16px; font-weight: bold; }
            QPushButton:hover { background-color: #286090; }
            QTabWidget::pane { border: 1px solid #2d2d3a; background: #1e1e24; }
            QTabBar::tab { background: #2a2a35; color: #b0b0b0; padding: 8px 16px; }
            QTabBar::tab:selected { background: #1e1e24; color: white; font-weight: bold; }
        """)
        
        os.makedirs(TEMP_EXTRACT_DIR, exist_ok=True)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Top Control Panel
        top_bar = QHBoxLayout()
        self.btn_parse = QPushButton("📊 Parse Live Security & PowerShell Timelines")
        self.btn_parse.clicked.connect(self.execute_log_triage)
        self.lbl_status = QLabel("Ready to analyze live operating system event streams.")
        top_bar.addWidget(self.btn_parse)
        top_bar.addWidget(self.lbl_status)
        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        self.tabs = QTabWidget()

        # Tab 1: Authentication Audits
        self.login_table = QTableWidget(0, 4)
        self.login_table.setHorizontalHeaderLabels(["Timestamp", "Target User / Account", "Logon Type ID", "Status Context"])
        self.login_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.login_table.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.login_table, "Authentication Audits (ID 4624)")

        # Tab 2: PowerShell Interceptions
        self.ps_table = QTableWidget(0, 3)
        self.ps_table.setHorizontalHeaderLabels(["Timestamp", "Event ID", "Intercepted Script Command Payload"])
        self.ps_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.ps_table.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.ps_table, "PowerShell Operational Logs (ID 4104)")

        main_layout.addWidget(self.tabs)

    def execute_log_triage(self):
        self.login_table.setRowCount(0)
        self.ps_table.setRowCount(0)
        self.lbl_status.setText("Extracting locked log paths via memory streaming...")
        self.repaint()

        logons = self.triage_evtx_file("Security.evtx", 4624)
        ps_scripts = self.triage_evtx_file("Microsoft-Windows-PowerShell%4Operational.evtx", 4104)

        self.lbl_status.setText(f"Analysis Complete: Extracted {logons} logon entries and {ps_scripts} PowerShell execution lines.")

    def triage_evtx_file(self, log_name, target_id):
        """Uses native wevtutil to decompress and query live binary event log channels directly."""
        count = 0
        import subprocess
        
        # Map out the exact live Windows log channel paths based on target ID
        if target_id == 4624:
            channel = "Security"
            query_filter = "*[System[(EventID=4624)]]"
        elif target_id == 4104:
            channel = "Microsoft-Windows-PowerShell/Operational"
            query_filter = "*[System[(EventID=4104)]]"
        else:
            return 0

        try:
            # Query the latest 100 events (/c:100) in reverse chronological order (/rd:true) as clean XML formatting (/f:xml)
            cmd = f'wevtutil.exe qe "{channel}" /q:"{query_filter}" /c:100 /rd:true /f:xml'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, errors='ignore')
            
            output_xml = result.stdout
            if not output_xml or len(output_xml.strip()) == 0:
                # If the channel returns nothing, it means no entries match or privileges are blocked
                raise PermissionError

            if target_id == 4624:
                # Extract timestamps and user profiles using regex out of clean cleartext XML blocks
                timestamps = re.findall(r'TimeCreated SystemTime=["\']([^"\']+)["\']', output_xml)
                usernames = re.findall(r'Data Name=["\']TargetUserName["\']>([^<]+)<', output_xml)
                logon_types = re.findall(r'Data Name=["\']LogonType["\']>([^<]+)<', output_xml)

                for idx, user in enumerate(usernames):
                    if user and not user.endswith('$') and user not in ["SYSTEM", "LOCAL SERVICE", "NETWORK SERVICE"]: 
                        row = self.login_table.rowCount()
                        self.login_table.insertRow(row)
                        
                        time_str = timestamps[idx].split(".")[0].replace("T", " ") if idx < len(timestamps) else "Unknown"
                        l_type = logon_types[idx] if idx < len(logon_types) else "N/A"
                        
                        # Map out human-readable Logon Types for the examiner
                        type_context = f"Type {l_type} (Interactive/Keyboard)" if l_type == "2" else f"Type {l_type} (Network Share/Remote)" if l_type == "3" else f"Type {l_type}"
                        
                        self.login_table.setItem(row, 0, QTableWidgetItem(time_str))
                        self.login_table.setItem(row, 1, QTableWidgetItem(user))
                        self.login_table.setItem(row, 2, QTableWidgetItem(type_context))
                        self.login_table.setItem(row, 3, QTableWidgetItem("Successful Logon Logged"))
                        count += 1

            elif target_id == 4104:
                timestamps = re.findall(r'TimeCreated SystemTime=["\']([^"\']+)["\']', output_xml)
                # Intercept full script string blocks pushed to the pipeline execution channel
                scripts = re.findall(r'Data Name=["\']ScriptBlockText["\']>([^<]+)<', output_xml)
                
                for idx, script_payload in enumerate(scripts):
                    clean_script = script_payload.strip()
                    if clean_script:
                        row = self.ps_table.rowCount()
                        self.ps_table.insertRow(row)
                        
                        time_str = timestamps[idx].split(".")[0].replace("T", " ") if idx < len(timestamps) else "Unknown"
                        
                        self.ps_table.setItem(row, 0, QTableWidgetItem(time_str))
                        self.ps_table.setItem(row, 1, QTableWidgetItem("4104"))
                        self.ps_table.setItem(row, 2, QTableWidgetItem(clean_script[:250].replace("&lt;", "<").replace("&gt;", ">")))
                        count += 1

        except PermissionError:
            # Drop a warning item directly inside the active UI view if access bounds trigger errors
            if target_id == 4624:
                row = self.login_table.rowCount()
                self.login_table.insertRow(row)
                self.login_table.setItem(row, 0, QTableWidgetItem("⚠ Access Denied: Relaunch app terminal using Run as Administrator to unlock channel access."))
            else:
                row = self.ps_table.rowCount()
                self.ps_table.insertRow(row)
                self.ps_table.setItem(row, 0, QTableWidgetItem("⚠ Access Denied: Relaunch app terminal using Run as Administrator to unlock channel access."))
        except Exception as e:
            print(f"[-] EVTX processing pipeline exception: {str(e)}")

        return count

    def closeEvent(self, event):
        if os.path.exists(TEMP_EXTRACT_DIR):
            try:
                shutil.rmtree(TEMP_EXTRACT_DIR)
            except Exception:
                pass
        event.accept()

def main_run(main_window_instance):
    dialog = EventLogParserDialog(main_window_instance)
    dialog.exec()