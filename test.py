import sys
from PyQt6 import uic
from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow, QFileDialog
import os
from datetime import datetime
from pypdf import PdfReader
import docx
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4

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
        
        # Connect the select button
        self.btn_select.clicked.connect(self.display_file_metadata)

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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Start the application by displaying the welcome screen first
    welcome_screen = WelcomeSplashDialog()
    welcome_screen.show()
    
    sys.exit(app.exec())