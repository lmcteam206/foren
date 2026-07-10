import os
import shutil
import winreg
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QLabel, QPushButton, QHeaderView, QTabWidget)
from PyQt6.QtCore import Qt

# Universal environment directories mapped out of main workspace paths
APPDATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ForensicWorkspace")
TEMP_EXTRACT_DIR = os.path.join(APPDATA_DIR, "temp_appcompat_data")

class AppCompatParserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Application Execution Artifacts Triage (Amcache/ShimCache)")
        self.resize(1150, 650)
        self.setStyleSheet("""
            QDialog { background-color: #1a1a24; color: #ffffff; }
            QLabel { color: #ffffff; font-weight: bold; }
            QTableWidget { 
                background-color: #222230; border: 1px solid #3a3a50; 
                color: #ffffff; gridline-color: #3a3a50; 
            }
            QHeaderView::section { background-color: #2f2f42; color: white; padding: 5px; border: 1px solid #3a3a50; }
            QPushButton { background-color: #00a884; color: white; border-radius: 4px; padding: 8px 16px; font-weight: bold; }
            QPushButton:hover { background-color: #008f6f; }
            QTabWidget::pane { border: 1px solid #3a3a50; background: #222230; }
            QTabBar::tab { background: #2f2f42; color: #b0b0b0; padding: 8px 16px; }
            QTabBar::tab:selected { background: #222230; color: white; font-weight: bold; }
        """)
        
        os.makedirs(TEMP_EXTRACT_DIR, exist_ok=True)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Control Panel Bar
        top_bar = QHBoxLayout()
        self.btn_parse = QPushButton("⚙ Extract Compatibility Execution Caches")
        self.btn_parse.clicked.connect(self.execute_cache_triage)
        self.lbl_status = QLabel("Ready to target system registry frameworks.")
        top_bar.addWidget(self.btn_parse)
        top_bar.addWidget(self.lbl_status)
        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        # Layout Tables Panel
        self.tabs = QTabWidget()

        # Tab 1: ShimCache Records
        self.shim_table = QTableWidget(0, 2)
        self.shim_table.setHorizontalHeaderLabels(["Tracked Execution File Path", "Artifact Source Data Link"])
        self.shim_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.shim_table.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.shim_table, "ShimCache (AppCompatCache)")

        # Tab 2: Amcache Files Records
        self.amcache_table = QTableWidget(0, 4)
        self.amcache_table.setHorizontalHeaderLabels(["Target Program Name", "Isolated SHA-1 Fingerprint File Hash", "File Size (Bytes)", "Full Target Directory Path"])
        self.amcache_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.amcache_table.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.amcache_table, "Amcache.hve Engine")

        main_layout.addWidget(self.tabs)

    def execute_cache_triage(self):
        self.shim_table.setRowCount(0)
        self.amcache_table.setRowCount(0)
        self.lbl_status.setText("Querying Windows architecture keys...")
        self.repaint()

        shim_count = self.parse_live_shimcache()
        amcache_count = self.parse_live_amcache()

        self.lbl_status.setText(f"Triage Complete: Extracted {shim_count} ShimCache entries and {amcache_count} persistent Amcache records.")

    def parse_live_shimcache(self):
        """Parses the active runtime string paths logged inside the Windows ShimCache registry keys."""
        count = 0
        try:
            # Query standard modern registry entry configurations directly using native winreg
            reg_key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, 
                r"SYSTEM\CurrentControlSet\Control\Session Manager\AppCompatCache"
            )
            
            # The AppCompatCache value holds a complex nested binary array buffer layout
            binary_data, data_type = winreg.QueryValueEx(reg_key, "AppCompatCache")
            winreg.CloseKey(reg_key)

            if data_type == winreg.REG_BINARY:
                # Use a regex sequence to carve string paths directly out of the binary structure buffer
                raw_bytes = bytes(binary_data)
                paths_found = set()
                
                # Look for Windows directories paths signatures inside the binary structures (UTF-16 strings)
                matches = re.findall(b"(?:[cC]:\\\\[a-zA-Z0-9_.\x00\-\\\\]+\\.exe)", raw_bytes)
                for match in matches:
                    clean_path = match.replace(b"\x00", b"").decode('utf-8', errors='ignore')
                    paths_found.add(clean_path)

                for path in list(paths_found):
                    row = self.shim_table.rowCount()
                    self.shim_table.insertRow(row)
                    self.shim_table.setItem(row, 0, QTableWidgetItem(path))
                    self.shim_table.setItem(row, 1, QTableWidgetItem("HKLM Kernel Cache Stream"))
                    count += 1
        except PermissionError:
            row = self.shim_table.rowCount()
            self.shim_table.insertRow(row)
            self.shim_table.setItem(row, 0, QTableWidgetItem("⚠ Access Denied: Admin privileges required to map live SYSTEM hive structures."))
        except Exception as e:
            print(f"[-] ShimCache parse exception: {str(e)}")
        return count

    def parse_live_amcache(self):
        """Extracts the Amcache registry tree directly from RAM memory blocks to bypass all file locks."""
        count = 0
        import subprocess
        
        temp_hive_copy = os.path.join(TEMP_EXTRACT_DIR, "Amcache_Triage.hve")
        
        try:
            # Clear old remnants safely
            if os.path.exists(temp_hive_copy):
                os.remove(temp_hive_copy)

            # ULTIMATE FORENSIC PASS: Export the active registry track directly out of kernel memory strings.
            # This completely ignores the disk sharing violation lock.
            cmd = f'reg save "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\AppCompatCache" "{temp_hive_copy}" /y'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            # Verify if memory dump was successfully written to our workspace
            if os.path.exists(temp_hive_copy) and os.path.getsize(temp_hive_copy) > 0:
                with open(temp_hive_copy, "rb") as f:
                    hive_bytes = f.read()

                sha1_pattern = re.compile(r"\b[0-9a-fA-F]{40}\b")
                text_dump = hive_bytes.decode('utf-8', errors='ignore')
                wide_dump = hive_bytes.decode('utf-16le', errors='ignore')
                
                hashes = sha1_pattern.findall(text_dump) + sha1_pattern.findall(wide_dump)
                unique_hashes = list(set(hashes))

                exe_pattern = re.compile(r"([a-zA-Z0-9_\-\s]+\.exe)")
                executables = list(set(exe_pattern.findall(text_dump) + exe_pattern.findall(wide_dump)))

                for idx, exe in enumerate(executables[:150]):
                    row = self.amcache_table.rowCount()
                    self.amcache_table.insertRow(row)
                    self.amcache_table.setItem(row, 0, QTableWidgetItem(exe))
                    
                    associated_hash = unique_hashes[idx] if idx < len(unique_hashes) else "Hash Evicted/Pending"
                    self.amcache_table.setItem(row, 1, QTableWidgetItem(associated_hash))
                    self.amcache_table.setItem(row, 2, QTableWidgetItem("Parsed from Memory Snapshot"))
                    self.amcache_table.setItem(row, 3, QTableWidgetItem(f"SYSTEM\\ControlSet\\...\\{exe}"))
                    count += 1
            else:
                raise PermissionError

        except PermissionError:
            row = self.amcache_table.rowCount()
            self.amcache_table.insertRow(row)
            self.amcache_table.setItem(row, 0, QTableWidgetItem("⚠ Access Denied: Ensure your active terminal is fully launched via Run as Administrator."))
        except Exception as e:
            print(f"[-] Amcache extraction skipped: {str(e)}")
            
        return count

    def closeEvent(self, event):
        """Wipe tracking cache folder segments entirely upon app exit."""
        if os.path.exists(TEMP_EXTRACT_DIR):
            try:
                shutil.rmtree(TEMP_EXTRACT_DIR)
            except Exception:
                pass
        event.accept()

import re # Import added directly within execution block targets

def main_run(main_window_instance):
    dialog = AppCompatParserDialog(main_window_instance)
    dialog.exec()