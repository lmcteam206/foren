import sys
from PyQt6 import uic
from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow, QFileDialog
import json
import urllib.request
import importlib.util
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QWidget, QCheckBox, QMessageBox
from PyQt6.QtCore import Qt
import os
from datetime import datetime
from pypdf import PdfReader
import docx
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from PyQt6.QtWidgets import QProgressBar

develmponet = True

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CURRENT_VERSION = "1.0.0"  # Increment this whenever you push a new release executable

def resource_path(relative_path):
    """ Resolves absolute paths for resources, handles both standard python execution and PyInstaller --onefile mode. """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# --- ROUTE PLUGINS BASED ON DEVELOPMENT FLAG ---
if develmponet:
    # Use local 'plugins' folder in the application directory
    ACTIVE_PLUGINS_DIR = os.path.join(BASE_DIR, "plugins")
else:
    # Fallback to standard AppData target
    APPDATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ForensicWorkspace")
    ACTIVE_PLUGINS_DIR = os.path.join(APPDATA_DIR, "plugins")

os.makedirs(ACTIVE_PLUGINS_DIR, exist_ok=True)

class MainWindowWorkspace(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi(resource_path("main.ui"), self)
        self.current_folder_path = ""
        self.connect_ui_signals()
        os.makedirs(ACTIVE_PLUGINS_DIR, exist_ok=True)
        self.load_enabled_plugins()

    def connect_ui_signals(self):
        """Initializes or restores button triggers cleanly after dynamic reloads."""
        if hasattr(self, "lbl_version"):
            self.lbl_version.setText(f"App Version: {CURRENT_VERSION}")

        if hasattr(self, "actionOpen_Folder"):
            self.actionOpen_Folder.triggered.connect(self.choose_directory)
        elif hasattr(self, "actionopen_folder"):
            self.actionopen_folder.triggered.connect(self.choose_directory)
        elif hasattr(self, "actionOpen"):
            self.actionOpen.triggered.connect(self.choose_directory)

        if hasattr(self, "actionplugins"):
            self.actionplugins.triggered.connect(self.open_plugin_store)
        elif hasattr(self, "actionPlugins"):
            self.actionPlugins.triggered.connect(self.open_plugin_store)
            
        if hasattr(self, "actionsettings"):
            self.actionsettings.triggered.connect(self.open_plugin_settings)
        elif hasattr(self, "actionSettings"):
            self.actionSettings.triggered.connect(self.open_plugin_settings)

        if hasattr(self, "btn_refresh_2"):
            self.btn_refresh_2.clicked.connect(self.refresh_workspace)
            
        if hasattr(self, "btn_check_update_2"):
            self.btn_check_update_2.clicked.connect(self.check_for_application_updates)
            
        if hasattr(self, "btn_select"):
            self.btn_select.clicked.connect(self.display_file_metadata)

    def refresh_workspace(self):
        """Clears old menu instances and dynamically updates current directory logs without dropping styles."""
        menubar = self.menuBar()
        menubar.clear()
        uic.loadUi(resource_path("main.ui"), self)
        self.connect_ui_signals()
        self.load_enabled_plugins()
        
        if self.current_folder_path:
            self.list_files.clear()
            try:
                for item in os.listdir(self.current_folder_path):
                    self.list_files.addItem(item)
                self.text_metadata.setText("[+] Workspace views and components refreshed successfully.")
            except Exception as e:
                self.text_metadata.setText(f"[-] Refresh folder failed: {str(e)}")
        else:
            self.text_metadata.setText("[+] Plugin layout registries re-cached.")

    def check_for_application_updates(self):
        """Fetches the version tag from GitHub and handles text/styles safely for both Buttons and Menu Actions."""
        target_btn = getattr(self, "btn_check_update_2", None)
        if not target_btn:
            return
            
        url = "https://raw.githubusercontent.com/lmcteam206/foren/main/version.txt"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                remote_version = response.read().decode('utf-8').strip()
                
            if remote_version == CURRENT_VERSION:
                status_text = f"✓ Latest Version ({CURRENT_VERSION})"
                target_btn.setText(status_text)
                target_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; border-radius: 4px; padding: 5px;")
            else:
                status_text = f"⚠ Update Available ({remote_version})"
                target_btn.setText(status_text)
                target_btn.setStyleSheet("background-color: #d9534f; color: white; font-weight: bold; border-radius: 4px; padding: 5px;")
                    
        except Exception as e:
            target_btn.setText("Update Check Failed")
            target_btn.setStyleSheet("background-color: #ffc107; color: black; padding: 5px;")

    def open_plugin_store(self):
        self.store_win = PluginStoreWindow(self)
        self.store_win.exec()

    def open_plugin_settings(self):
        self.settings_win = PluginSettingsWindow(self)
        self.settings_win.exec()

    def load_enabled_plugins(self):
        """Discovers downloaded plugins and executes them if enabled inside settings."""
        config_path = os.path.join(ACTIVE_PLUGINS_DIR, "config.json")
        if not os.path.exists(config_path):
            return
            
        with open(config_path, "r") as f:
            config = json.load(f)

        for plugin_name, data in config.items():
            if data.get("enabled", False):
                script_path = os.path.join(ACTIVE_PLUGINS_DIR, plugin_name, f"{plugin_name}.py")
                if os.path.exists(script_path):
                    menu = self.menuBar().addMenu(data.get("title", plugin_name))
                    action = menu.addAction("Launch Core Utility")
                    action.triggered.connect(lambda checked, p=script_path: self.run_plugin_script(p))

    def run_plugin_script(self, script_path):
        """Loads and runs the isolated custom .py plugin file cleanly on-the-fly."""
        try:
            spec = importlib.util.spec_from_file_location("plugin_mod", script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "main_run"):
                module.main_run(self)
        except Exception as e:
            print(f"[-] Failed executing modular extension: {str(e)}")

    def choose_directory(self):
        folder_selected = QFileDialog.getExistingDirectory(self, "Select Target Folder")
        if folder_selected:
            self.current_folder_path = folder_selected
            self.list_files.clear()
            try:
                for item in os.listdir(folder_selected):
                    self.list_files.addItem(item)
            except Exception as e:
                self.text_metadata.setText(f"[-] Error parsing directory: {str(e)}")

    def display_file_metadata(self):
        selected_items = self.list_files.selectedItems()
        if not selected_items:
            self.text_metadata.setText("[-] Warning: Please select a file from the list first.")
            return
            
        file_name = selected_items[0].text()
        full_file_path = os.path.join(self.current_folder_path, file_name)
        
        if os.path.isdir(full_file_path):
            self.text_metadata.setText(f"Target: {file_name}\nType: Directory/Folder\nPath: {full_file_path}")
            return

        def parse_pdf_date(date_str):
            if not date_str or not isinstance(date_str, str):
                return date_str
            clean_str = date_str.replace("D:", "").replace("'", "")
            try:
                core_date = clean_str[:14]
                dt = datetime.strptime(core_date, "%Y%m%d%H%M%S")
                tz = clean_str[14:]
                return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} ({tz})" if tz else dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                return date_str

        if file_name.lower().endswith('.pdf'):
            try:
                reader = PdfReader(full_file_path)
                meta = reader.metadata
                report = "=== INTERNAL PDF FORENSIC REPORT ===\n\n"
                report += f"File Name:        {file_name}\n"
                report += f"Total Pages:      {len(reader.pages)}\n"
                report += f"Is Encrypted:     {reader.is_encrypted}\n"
                if meta:
                    report += f"Title:            {meta.title if meta.title else ''}\n"
                    report += f"Author:           {meta.author if meta.author else ''}\n"
                    report += f"Subject:          {meta.subject if meta.subject else ''}\n"
                    report += f"Keywords:         {meta.keywords if meta.keywords else ''}\n"
                    report += f"Creator:          {meta.creator if meta.creator else ''}\n"
                    report += f"Producer:         {meta.producer if meta.producer else ''}\n"
                    report += f"Creation Date:    {parse_pdf_date(meta.get('/CreationDate'))}\n"
                    report += f"Mod Date:         {parse_pdf_date(meta.get('/ModDate'))}\n"
                    
                    report += "\n--- Custom Embedded / Application Properties ---\n"
                    custom_found = False
                    internal_structural_keys = ['/Type', '/Pages', '/Metadata', '/Extensions', '/Count', '/Kids', '/Contents']
                    for key, value in meta.items():
                        if key in ['/Title', '/Author', '/Subject', '/Keywords', '/Creator', '/Producer', '/CreationDate', '/ModDate']:
                            continue
                        if key in internal_structural_keys or "IndirectObject" in str(value):
                            continue
                        display_key = key.lstrip('/')
                        report += f"{display_key:<18}: {value}\n"
                        custom_found = True
                    if not custom_found:
                        report += "[No custom application tags found]\n"
                else:
                    report += "[-] Notice: PDF contains no internal metadata dictionary.\n"
                report += "\n===================================="
                self.text_metadata.setText(report)
                return
            except Exception:
                pass

        elif file_name.lower().endswith('.docx'):
            try:
                doc = docx.Document(full_file_path)
                props = doc.core_properties
                report = "=== INTERNAL WORD (.DOCX) FORENSIC REPORT ===\n\n"
                report += f"File Name:        {file_name}\n"
                report += f"Author/Creator:   {props.author if props.author else 'Unknown'}\n"
                report += f"Last Modified By: {props.last_modified_by if props.last_modified_by else 'Unknown'}\n"
                report += f"Created Date:     {props.created.strftime('%Y-%m-%d %H:%M:%S') if props.created else 'Unknown'}\n"
                report += f"Modified Date:    {props.modified.strftime('%Y-%m-%d %H:%M:%S') if props.modified else 'Unknown'}\n"
                report += f"Revision Number:  {props.revision if props.revision else 'Unknown'}\n"
                report += f"Title:            {props.title if props.title else ''}\n"
                report += f"Subject:          {props.subject if props.subject else ''}\n"
                report += f"Category:         {props.category if props.category else ''}\n"
                report += f"Comments:         {props.comments if props.comments else ''}\n"
                report += "\n============================================"
                self.text_metadata.setText(report)
                return
            except Exception:
                pass

        elif file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.webp')):
            try:
                img = Image.open(full_file_path)
                report = "=== DEEP IMAGE FORENSIC REPORT ===\n\n"
                report += f"File Name:        {file_name}\n"
                report += f"Resolution:       {img.width} x {img.height} pixels\n"
                report += f"Color Mode:       {img.mode}\n"
                report += f"Format Standard:  {img.format}\n\n"
                exif_data = img._getexif()
                if exif_data:
                    report += "--- Embedded EXIF / Hardware Tags ---\n"
                    gps_info = {}
                    for tag_id, value in exif_data.items():
                        tag_name = TAGS.get(tag_id, tag_id)
                        if tag_name == "GPSInfo":
                            gps_info = value
                            continue
                        if isinstance(value, bytes) and len(value) > 40:
                            value = f"[Raw Data Blob: {len(value)} bytes]"
                        report += f"{str(tag_name):<18}: {value}\n"
                    if gps_info:
                        report += "\n--- Embedded GPS Telemetry Data ---\n"
                        for gps_id in gps_info:
                            gps_tag = GPSTAGS.get(gps_id, gps_id)
                            gps_val = gps_info[gps_id]
                            report += f"GPS_{str(gps_tag):<14}: {gps_val}\n"
                else:
                    report += "[No embedded EXIF metadata discovered]\n"
                report += "\n===================================="
                self.text_metadata.setText(report)
                img.close()
                return
            except Exception:
                pass            

        try:
            file_stats = os.stat(full_file_path)
            report = f"=== SYSTEM FILE METADATA REPORT ===\n\n"
            report += f"File Name:     {file_name}\n"
            report += f"File Size:     {file_stats.st_size} Bytes\n"
            self.text_metadata.setText(report)
        except Exception as e:
            self.text_metadata.setText(f"[-] Failed to extract any metadata targets: {str(e)}")

class WelcomeSplashDialog(QDialog):
    def __init__(self):
        super().__init__()
        uic.loadUi(resource_path("info.ui"), self)
        self.btn_start.clicked.connect(self.launch_main_workspace)
        self.btn_quit.clicked.connect(self.close)
        self.main_workspace = None

    def launch_main_workspace(self):
        self.main_workspace = MainWindowWorkspace()
        self.main_workspace.show()
        self.accept() 

class PluginStoreWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Forensic Plugin Registry Store")
        self.resize(650, 550)
        self.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
  
        self.github_user = "lmcteam206"
        self.github_repo = "foren"
        self.registry_url = f"https://raw.githubusercontent.com/{self.github_user}/{self.github_repo}/main/plugins/plugins_registry.json"
        
        layout = QVBoxLayout(self)
        label = QLabel("### Available Community Plugins Marketplace ###")
        label.setTextFormat(Qt.TextFormat.MarkdownText)
        layout.addWidget(label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        
        self.local_config = self.load_local_config()
        self.remote_plugins = []
        self.fetch_remote_registry()
        self.populate_marketplace()
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def load_local_config(self):
        config_path = os.path.join(ACTIVE_PLUGINS_DIR, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def fetch_remote_registry(self):
        try:
            req = urllib.request.Request(self.registry_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                self.remote_plugins = json.loads(response.read().decode())
        except Exception as e:
            print(f"[-] Failed to fetch remote registry: {str(e)}")
            self.remote_plugins = []

    def populate_marketplace(self):
        if not self.remote_plugins:
            error_lbl = QLabel("<font color='#d9534f'>[-] Unable to load store catalog.</font>")
            self.scroll_layout.addWidget(error_lbl)
            return

        for item in self.remote_plugins:
            card = QWidget()
            card.setStyleSheet("background-color: #2d2d2d; border-radius: 6px; padding: 12px; margin-bottom: 8px;")
            card_layout = QVBoxLayout(card)

            # Determine local version and status
            plugin_id = item["id"]
            remote_ver = item.get("version", "1.0.0")
            local_plugin_data = self.local_config.get(plugin_id, {})
            local_ver = local_plugin_data.get("version")
            
            status_text = f"Version: v{remote_ver}"
            is_update = False
            is_installed = False

            if local_ver:
                is_installed = True
                if local_ver != remote_ver:
                    status_text = f"Update Available! (Local: v{local_ver} ➔ Remote: v{remote_ver})"
                    is_update = True
                else:
                    status_text = f"✓ Installed (v{local_ver})"

            title_layout = QHBoxLayout()
            title = QLabel(f"<span style='font-size: 14px; font-weight: bold;'>{item['title']}</span>")
            version_lbl = QLabel(f"<span style='color: #888888;'>{status_text}</span>")
            title_layout.addWidget(title)
            title_layout.addStretch()
            title_layout.addWidget(version_lbl)
            card_layout.addLayout(title_layout)

            desc = QLabel(item['desc'])
            desc.setWordWrap(True)
            card_layout.addWidget(desc)
            
            # --- MAXIMUM HONESTY DISCLOSURE SECTION ---
            features_text = "• " + "\n• ".join(item.get("features", ["General functionality layers"]))
            cons_text = "• " + "\n• ".join(item.get("cons", ["None logged"]))
            
            disclosure_lbl = QLabel(
                f"<font color='#00a884'><b>Key Features:</b></font><br/>{features_text}<br/>"
                f"<font color='#ffc107'><b>Limitations/Cons:</b></font><br/>{cons_text}"
            )
            disclosure_lbl.setWordWrap(True)
            card_layout.addWidget(disclosure_lbl)

            if "warning" in item and item["warning"]:
                warn_lbl = QLabel(f"<font color='#d9534f'><b>⚠ FORENSIC WARNING:</b> {item['warning']}</font>")
                warn_lbl.setWordWrap(True)
                card_layout.addWidget(warn_lbl)

            # --- DYNAMIC UPDATE / INSTALL BUTTON TRIGGER ---
            btn_install = QPushButton()
            if is_update:
                btn_install.setText(f"Update Plugin to v{remote_ver}")
                btn_install.setStyleSheet("background-color: #d9534f; color: white; font-weight: bold; padding: 6px;")
            elif is_installed:
                btn_install.setText("Reinstall Package")
                btn_install.setStyleSheet("background-color: #555555; color: white; padding: 5px;")
            else:
                btn_install.setText("Install Plugin Package")
                btn_install.setStyleSheet("background-color: #007acc; font-weight: bold; padding: 6px;")
            
            progress_bar = QProgressBar()
            progress_bar.setStyleSheet("QProgressBar { background-color: #1e1e1e; text-align: center; } QProgressBar::chunk { background-color: #28a745; }")
            progress_bar.setVisible(False)

            btn_install.clicked.connect(lambda checked, i=item, btn=btn_install, pb=progress_bar: self.download_package(i, btn, pb))

            card_layout.addWidget(btn_install)
            card_layout.addWidget(progress_bar)
            self.scroll_layout.addWidget(card)

    def download_package(self, item, target_btn, progress_bar):
        try:
            target_btn.setEnabled(False)
            progress_bar.setVisible(True)
            progress_bar.setValue(0)
            
            dest_dir = os.path.join(ACTIVE_PLUGINS_DIR, item["id"])
            os.makedirs(dest_dir, exist_ok=True)
            total_files = len(item["files"])
            
            for idx, filename in enumerate(item["files"], start=1):
                remote_file_url = f"https://raw.githubusercontent.com/{self.github_user}/{self.github_repo}/main/plugins/{item['id']}/{filename}"
                local_save_path = os.path.join(dest_dir, filename)
                
                urllib.request.urlretrieve(remote_file_url, local_save_path)
                
                percentage = int((idx / total_files) * 100)
                progress_bar.setValue(percentage)
                QApplication.processEvents()

            config_path = os.path.join(ACTIVE_PLUGINS_DIR, "config.json")
            config = {}
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = json.load(f)

            # Store both title, version code, and enabled state locally
            config[item["id"]] = {
                "title": item["title"], 
                "enabled": True,
                "version": item.get("version", "1.0.0")
            }
            with open(config_path, "w") as f:
                json.dump(config, f, indent=4)

            target_btn.setText("✓ Complete (Restart App)")
            target_btn.setStyleSheet("background-color: #28a745; color: white;")
        except Exception as e:
            target_btn.setEnabled(True)
            target_btn.setText("Retry Operation")
            progress_bar.setFormat(f"Failure: {str(e)}")

class PluginSettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Plugin Configuration Manager")
        self.resize(400, 350)
        self.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
        
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(QLabel("<h3>Enable/Disable Installed Systems</h3>"))
        
        self.config_path = os.path.join(ACTIVE_PLUGINS_DIR, "config.json")
        self.check_boxes = {}
        self.load_settings_list()
        
        btn_save = QPushButton("Save Settings & Apply Configurations")
        btn_save.setStyleSheet("background-color: #28a745; font-weight: bold; padding: 6px;")
        btn_save.clicked.connect(self.save_configurations)
        self.layout.addWidget(btn_save)

    def load_settings_list(self):
        if not os.path.exists(self.config_path):
            self.layout.addWidget(QLabel("[No external plugins downloaded yet]"))
            return

        with open(self.config_path, "r") as f:
            self.config = json.load(f)

        for plugin_id, data in self.config.items():
            version_str = f" (v{data['version']})" if "version" in data else ""
            cb = QCheckBox(f"{data.get('title', plugin_id)}{version_str}")
            cb.setChecked(data.get("enabled", False))
            self.layout.addWidget(cb)
            self.check_boxes[plugin_id] = cb

    def save_configurations(self):
        if os.path.exists(self.config_path):
            for plugin_id, cb in self.check_boxes.items():
                self.config[plugin_id]["enabled"] = cb.isChecked()
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=4)
        self.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    welcome_screen = WelcomeSplashDialog()
    welcome_screen.show()
    sys.exit(app.exec())