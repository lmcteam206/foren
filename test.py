import sys
from PyQt6 import uic
from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow, QFileDialog
import json
import urllib.request
import importlib.util
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QWidget, QCheckBox
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
      # Force the script to look at its own source directory for storage
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CURRENT_VERSION = "1.0.0"  # Increment this whenever you push a new release executable
        # Update your folder creation line to look like this:
os.makedirs(os.path.join(BASE_DIR, "plugins"), exist_ok=True)

class MainWindowWorkspace(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("main.ui", self)
        
        self.current_folder_path = ""
        
        # Check different naming variations that Designer might have assigned
        if hasattr(self, "actionOpen_Folder"):
            self.actionOpen_Folder.triggered.connect(self.choose_directory)
        elif hasattr(self, "actionopen_folder"):
            self.actionopen_folder.triggered.connect(self.choose_directory)
        elif hasattr(self, "actionOpen"):
            self.actionOpen.triggered.connect(self.choose_directory)
        else:
            print("[-] Warning: Could not find the menu Action object name!")
            print("Check the 'Action Editor' panel in Designer to see what it named your menu item.")
        # 4. Connect Plugin & Settings Menu items
        if hasattr(self, "actionplugins"):
            self.actionplugins.triggered.connect(self.open_plugin_store)
        elif hasattr(self, "actionPlugins"):
            self.actionPlugins.triggered.connect(self.open_plugin_store)
            
        if hasattr(self, "actionsettings"):
            self.actionsettings.triggered.connect(self.open_plugin_settings)
        elif hasattr(self, "actionSettings"):
            self.actionSettings.triggered.connect(self.open_plugin_settings)
        # Connect the Refresh and Update actions
        if hasattr(self, "btn_refresh_2"):
            self.btn_refresh_2.clicked.connect(self.refresh_workspace)
            
        if hasattr(self, "btn_check_update_2"):
            self.btn_check_update_2.clicked.connect(self.check_for_application_updates)
        # Create local storage directory for downloads if it doesn't exist
        os.makedirs("plugins", exist_ok=True)
        self.load_enabled_plugins()
        # Connect the select button
        self.btn_select.clicked.connect(self.display_file_metadata)
    def refresh_workspace(self):
        """Clears old menu instances and dynamically updates current directory logs."""
        # 1. Clear any previously generated dynamic plugin menus
        menubar = self.menuBar()
        menubar.clear()
        
        # 2. Re-read UI native actions if Qt Designer drops them on clean clear routines
        uic.loadUi("main.ui", self)
        
        # 3. Reload dynamic plugin configurations cleanly on the fly
        self.load_enabled_plugins()
        
        # 4. Refresh target folder files list if a directory tracking loop is active
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
        target_btn = getattr(self, "btn_check_update", None)
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
                # Apply color styling only if it's a real button widget
                if hasattr(target_btn, "setStyleSheet"):
                    target_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; border-radius: 4px; padding: 5px;")
            else:
                status_text = f"⚠ Update Available ({remote_version})"
                target_btn.setText(status_text)
                if hasattr(target_btn, "setStyleSheet"):
                    target_btn.setStyleSheet("background-color: #d9534f; color: white; font-weight: bold; border-radius: 4px; padding: 5px;")
                    
        except Exception as e:
            target_btn.setText("Update Check Failed (404 / Timeout)")
            if hasattr(target_btn, "setStyleSheet"):
                target_btn.setStyleSheet("background-color: #ffc107; color: black; padding: 5px;")
    def open_plugin_store(self):
        self.store_win = PluginStoreWindow(self)
        self.store_win.exec()

    def open_plugin_settings(self):
        self.settings_win = PluginSettingsWindow(self)
        self.settings_win.exec()

    def load_enabled_plugins(self):
        """Discovers downloaded plugins and executes them if enabled inside settings."""
        config_path = os.path.join("plugins", "config.json")
        if not os.path.exists(config_path):
            return
            
        with open(config_path, "r") as f:
            config = json.load(f)

        # Dynamically inject actions into your workspace top-bar menu for enabled mods
        for plugin_name, data in config.items():
            if data.get("enabled", False):
                script_path = os.path.join("plugins", plugin_name, f"{plugin_name}.py")
                if os.path.exists(script_path):
                    # Create an entry option on your menu bar for this custom tool
                    menu = self.menuBar().addMenu(data.get("title", plugin_name))
                    action = menu.addAction("Launch Core Utility")
                    action.triggered.connect(lambda checked, p=script_path: self.run_plugin_script(p))

    def run_plugin_script(self, script_path):
        """Loads and runs the isolated custom .py plugin file cleanly on-the-fly."""
        try:
            spec = importlib.util.spec_from_file_location("plugin_mod", script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Looks inside your plugin .py file for a structural function named main_run()
            if hasattr(module, "main_run"):
                module.main_run(self)
        except Exception as e:
            print(f"[-] Failed executing modular extension: {str(e)}")
    def choose_directory(self):
        # Open the Windows directory picker dialog
        folder_selected = QFileDialog.getExistingDirectory(self, "Select Target Folder")
        
        if folder_selected:
            self.current_folder_path = folder_selected
            self.list_files.clear() # Clear any old entries from the list box
            
            try:
                # Read all items in the folder and add them to the left list widget
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

        # Helper function to clean up raw PDF date strings (D:YYYYMMDDHHMMSS...)
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

        # ==========================================
        # 1. PARSE INTERNAL PDF METADATA
        # ==========================================
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
            except Exception as e:
                pass # Fall through to basic filesystem metadata if parsing fails

        # ==========================================
        # 2. PARSE INTERNAL WORD METADATA (.DOCX)
        # ==========================================
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
            except Exception as e:
                pass

        # ==========================================
        # 3. PARSE LEGACY BINARY WORD METADATA (.DOC)
        # ==========================================
        elif file_name.lower().endswith('.doc'):
            try:
                # Legacy .doc files are OLE compound binary structures. 
                # We can extract strings securely to look for metadata signatures.
                with open(full_file_path, 'rb') as f:
                    data = f.read()
                
                # Scrape printable text strings out of the binary blob
                strings = []
                current_str = []
                for char in data:
                    if 32 <= char <= 126: # Valid ASCII printable character spectrum
                        current_str.append(chr(char))
                    else:
                        if len(current_str) >= 4:
                            strings.append("".join(current_str))
                        current_str = []
                
                # Look for authoring applications or document paths injected in old formats
                report = "=== LEGACY WORD (.DOC) RECONNAISSANCE ===\n\n"
                report += f"File Name:        {file_name}\n"
                report += "[*] Scraped Application Metadata Strings:\n"
                
                metadata_keywords = ["Microsoft", "Word", "Normal.dotm", "Title", "Author", "Template"]
                found_keywords = set()
                for s in strings:
                    for kw in metadata_keywords:
                        if kw.lower() in s.lower() and len(s) < 100:
                            found_keywords.add(s.strip())
                
                for item in list(found_keywords)[:15]: # Show top 15 most interesting findings
                    report += f" -> {item}\n"
                    
                report += "\n[!] Note: Legacy .doc files require raw string mining. See full filesystem parameters below.\n"
                report += "\n=========================================="
                
                # Append standard file logs to it for completion
                file_stats = os.stat(full_file_path)
                report += f"\n\nFile Size: {file_stats.st_size} Bytes\n"
                report += f"Created (C): {datetime.fromtimestamp(file_stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S')}\n"
                
                self.text_metadata.setText(report)
                return
            except Exception:
                pass
# ==========================================
        # 3.5 PARSE INTERNAL AUDIO METADATA (.MP3)
        # ==========================================
        elif file_name.lower().endswith('.mp3'):
            try:
                audio = MP3(full_file_path)
                
                report = "=== INTERNAL AUDIO (.MP3) FORENSIC REPORT ===\n\n"
                report += f"File Name:        {file_name}\n"
                report += f"Duration:         {audio.info.length:.2f} seconds\n"
                report += f"Bitrate:          {audio.info.bitrate // 1000} kbps\n"
                report += f"Sample Rate:      {audio.info.sample_rate} Hz\n"
                report += f"Channels:         {audio.info.channels}\n\n"
                
                report += "--- Embedded ID3 Metadata Tags ---\n"
                if audio.tags:
                    for tag, value in audio.tags.items():
                        # Standard human-readable mapping descriptions
                        tag_desc = {
                            'TIT2': 'Title', 'TPE1': 'Lead Artist', 'TALB': 'Album',
                            'TYER': 'Year', 'TDRC': 'Recording Date', 'COMM': 'Comments',
                            'TCON': 'Genre', 'TCOM': 'Composer', 'TSSE': 'Encoder Settings'
                        }.get(tag, tag)
                        report += f"{tag_desc:<18}: {value}\n"
                else:
                    report += "[No embedded ID3 tags discovered]\n"
                
                report += "\n============================================"
                self.text_metadata.setText(report)
                return
            except Exception as e:
                pass

        # ==========================================
        # 3.6 PARSE INTERNAL VIDEO METADATA (.MP4)
        # ==========================================
        elif file_name.lower().endswith('.mp4'):
            try:
                video = MP4(full_file_path)
                
                report = "=== INTERNAL VIDEO (.MP4) FORENSIC REPORT ===\n\n"
                report += f"File Name:        {file_name}\n"
                report += f"Duration:         {video.info.length:.2f} seconds\n"
                report += f"Bitrate:          {video.info.bitrate // 1000 if video.info.bitrate else 0} kbps\n"
                
                report += "\n--- Container Atom Tags ---\n"
                if video.tags:
                    for tag, value in video.tags.items():
                        # Strip standard Apple container prefix if present
                        display_key = tag.lstrip('\xa9')
                        # Translate common sub-atoms
                        display_key = {'nam': 'Title', 'ART': 'Artist', 'alb': 'Album', 'day': 'Creation Date/Year'}.get(display_key, display_key)
                        report += f"{display_key:<18}: {value}\n"
                else:
                    report += "[No metadata atoms discovered inside container]\n"
                
                report += "\n============================================"
                self.text_metadata.setText(report)
                return
            except Exception as e:
                pass
# ==========================================
        # 3.7 PARSE DEEP IMAGE METADATA (EXIF / GPS)
        # ==========================================
        elif file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.webp')):
            try:
                img = Image.open(full_file_path)
                
                report = "=== DEEP IMAGE FORENSIC REPORT ===\n\n"
                report += f"File Name:        {file_name}\n"
                report += f"Resolution:       {img.width} x {img.height} pixels\n"
                report += f"Color Mode:       {img.mode}\n"
                report += f"Format Standard:  {img.format}\n\n"
                
                # Extract raw Exchangeable Image File (EXIF) dictionary data
                exif_data = img._getexif()
                
                if exif_data:
                    report += "--- Embedded EXIF / Hardware Tags ---\n"
                    gps_info = {}
                    
                    for tag_id, value in exif_data.items():
                        tag_name = TAGS.get(tag_id, tag_id)
                        
                        # Hold onto GPS data dictionary for secondary deep parsing
                        if tag_name == "GPSInfo":
                            gps_info = value
                            continue
                            
                        # Format long metadata structures or raw bytes to keep report clean
                        if isinstance(value, bytes):
                            if len(value) > 40:
                                value = f"[Raw Data Blob: {len(value)} bytes]"
                        
                        report += f"{str(tag_name):<18}: {value}\n"
                    
                    # Process geographical telemetry maps if they exist
                    if gps_info:
                        report += "\n--- Embedded GPS Telemetry Data ---\n"
                        for gps_id in gps_info:
                            gps_tag = GPSTAGS.get(gps_id, gps_id)
                            gps_val = gps_info[gps_id]
                            report += f"GPS_{str(gps_tag):<14}: {gps_val}\n"
                else:
                    report += "[No embedded EXIF metadata or GPS logs discovered in image dictionary]\n"
                
                report += "\n============================================"
                self.text_metadata.setText(report)
                img.close()
                return
            except Exception as e:
                pass            
        # ==========================================
        # 4. FALLBACK: STANDARD FILESYSTEM METADATA
        # ==========================================
        try:
            file_stats = os.stat(full_file_path)
            modified_time = datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            accessed_time = datetime.fromtimestamp(file_stats.st_atime).strftime('%Y-%m-%d %H:%M:%S')
            created_time  = datetime.fromtimestamp(file_stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
            
            report = f"=== SYSTEM FILE METADATA REPORT ===\n\n"
            report += f"File Name:     {file_name}\n"
            report += f"Absolute Path: {full_file_path}\n"
            report += f"File Size:     {file_stats.st_size} Bytes\n\n"
            report += f"Modified (M):  {modified_time}\n"
            report += f"Accessed (A):  {accessed_time}\n"
            report += f"Created (C):   {created_time}\n"
            report += f"\n================================="
            
            self.text_metadata.setText(report)
        except Exception as e:
            self.text_metadata.setText(f"[-] Failed to extract any metadata targets: {str(e)}")
class WelcomeSplashDialog(QDialog):
    def __init__(self):
        super().__init__()
        # Load your welcome splash layout (the left window in your image)
        uic.loadUi("info.ui", self)
        
        # Link your welcome screen buttons to actions
        self.btn_start.clicked.connect(self.launch_main_workspace)
        self.btn_quit.clicked.connect(self.close)
        
        # This variable will hold our main workspace instance later
        self.main_workspace = None

    def launch_main_workspace(self):
        # 1. Instantiate the main forensic workspace window
        self.main_workspace = MainWindowWorkspace()
        
        # 2. Display the main workspace window to your dad
        self.main_workspace.show()
        
        # 3. Close the welcome screen dialog automatically
        self.accept() 

class PluginStoreWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Forensic Plugin Registry Store")
        self.resize(550, 450)
        self.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
  
        # --- CONFIGURATION MATCHING YOUR REPOSITORY ---
        self.github_user = "lmcteam206"
        self.github_repo = "foren"
        # URL pointing to your online central index file
        # Change this line inside your PluginStoreWindow.__init__ method:
        self.registry_url = f"https://raw.githubusercontent.com/{self.github_user}/{self.github_repo}/main/plugins/plugins_registry.json"
        
        layout = QVBoxLayout(self)
        label = QLabel("### Available Community Plugins Marketplace ###")
        label.setTextFormat(Qt.TextFormat.MarkdownText)
        layout.addWidget(label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        
        self.remote_plugins = []
        # Fetch the registry live from GitHub instead of hardcoding
        self.fetch_remote_registry()
        
        self.populate_marketplace()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def fetch_remote_registry(self):
        """Downloads the central plugins database file on the fly with custom browser headers."""
        try:
            # Set up a generic browser header layout
            req = urllib.request.Request(self.registry_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req) as response:
                self.remote_plugins = json.loads(response.read().decode())
        except Exception as e:
            print(f"[-] Failed to fetch remote plugins manifest index: {str(e)}")
            self.remote_plugins = []

    def populate_marketplace(self):
        if not self.remote_plugins:
            error_lbl = QLabel("<font color='#d9534f'>[-] Unable to load store catalog. Check connection or registry.json path.</font>")
            self.scroll_layout.addWidget(error_lbl)
            return

        for item in self.remote_plugins:
            card = QWidget()
            card.setStyleSheet("background-color: #2d2d2d; border-radius: 6px; padding: 10px; margin-bottom: 5px;")
            card_layout = QVBoxLayout(card)

            title = QLabel(f"<b>{item['title']}</b>")
            desc = QLabel(item['desc'])
            desc.setWordWrap(True)
            
            # Format list array to human-readable string text
            files_str = ", ".join(item["files"])
            files = QLabel(f"<font color='#888888'>Assets to fetch: {files_str}</font>")
            
            btn_install = QPushButton("Install Plugin Package")
            btn_install.setStyleSheet("background-color: #007acc; font-weight: bold; padding: 5px;")
            
            # Hidden track parameters embedded to help track local component instances later
            progress_bar = QProgressBar()
            progress_bar.setStyleSheet("QProgressBar { background-color: #1e1e1e; border-radius: 4px; text-align: center; } QProgressBar::chunk { background-color: #28a745; }")
            progress_bar.setVisible(False)

            # Link action passing along its own visual cards and controls
            btn_install.clicked.connect(lambda checked, i=item, btn=btn_install, pb=progress_bar: self.download_package(i, btn, pb))

            card_layout.addWidget(title)
            card_layout.addWidget(desc)
            card_layout.addWidget(files)
            card_layout.addWidget(btn_install)
            card_layout.addWidget(progress_bar)
            self.scroll_layout.addWidget(card)

    def download_package(self, item, target_btn, progress_bar):
        try:
            target_btn.setEnabled(False)
            progress_bar.setVisible(True)
            progress_bar.setValue(0)
            
            dest_dir = os.path.join("plugins", item["id"])
            os.makedirs(dest_dir, exist_ok=True)

            total_files = len(item["files"])
            
            for idx, filename in enumerate(item["files"], start=1):
                # Dynamically construct target remote paths matching repository file configurations
                remote_file_url = f"https://raw.githubusercontent.com/{self.github_user}/{self.github_repo}/main/plugins/{item['id']}/{filename}"
                local_save_path = os.path.join(dest_dir, filename)
                
                # Fetch asset from GitHub
                urllib.request.urlretrieve(remote_file_url, local_save_path)
                
                # Calculate and update progression
                percentage = int((idx / total_files) * 100)
                progress_bar.setValue(percentage)
                progress_bar.setFormat(f"Downloaded {filename} ({percentage}%)")
                
                # Process window updates safely between execution phases
                QApplication.processEvents()

            # Force the download path to stick to your script's home folder
            dest_dir = os.path.join(BASE_DIR, "plugins", item["id"])
            os.makedirs(dest_dir, exist_ok=True)

            # And update the config path matching it:
            config_path = os.path.join(BASE_DIR, "plugins", "config.json")
            config = {}
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = json.load(f)

            config[item["id"]] = {"title": item["title"], "enabled": True}
            with open(config_path, "w") as f:
                json.dump(config, f, indent=4)

            target_btn.setText("✓ Installed Successfully")
            progress_bar.setFormat("Complete!")
        except Exception as e:
            target_btn.setEnabled(True)
            target_btn.setText("Retry Installation")
            progress_bar.setFormat(f"Extraction Failure: {str(e)}")

class PluginSettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Plugin Configuration Manager")
        self.resize(400, 300)
        self.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
        
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(QLabel("<h3>Enable/Disable Installed Systems</h3>"))
        
        self.config_path = os.path.join("plugins", "config.json")
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
            cb = QCheckBox(data.get("title", plugin_id))
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
    
    # Start the application by displaying the welcome screen first
    welcome_screen = WelcomeSplashDialog()
    welcome_screen.show()
    
    sys.exit(app.exec())