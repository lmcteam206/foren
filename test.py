import sys
from PyQt6 import uic
from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow, QFileDialog
import os
from datetime import datetime

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
        # Find which item is highlighted in the left list box
        selected_items = self.list_files.selectedItems()
        if not selected_items:
            self.text_metadata.setText("[-] Warning: Please select a file from the list first.")
            return
            
        file_name = selected_items[0].text()
        full_file_path = os.path.join(self.current_folder_path, file_name)
        
        if os.path.isdir(full_file_path):
            self.text_metadata.setText(f"Target: {file_name}\nType: Directory/Folder\nPath: {full_file_path}")
            return

        try:
            # Query filesystem status data logs for the target file
            file_stats = os.stat(full_file_path)
            
            # Convert structural timestamp flags to readable string text format
            modified_time = datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            accessed_time = datetime.fromtimestamp(file_stats.st_atime).strftime('%Y-%m-%d %H:%M:%S')
            created_time  = datetime.fromtimestamp(file_stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
            
            # Format the output report string
            report = f"=== FORENSIC METADATA REPORT ===\n\n"
            report += f"File Name:     {file_name}\n"
            report += f"Absolute Path: {full_file_path}\n"
            report += f"File Size:     {file_stats.st_size} Bytes\n\n"
            report += f"Modified (M):  {modified_time}\n"
            report += f"Accessed (A):  {accessed_time}\n"
            report += f"Created (C):   {created_time}\n"
            report += f"\n================================="
            
            # Push the text block onto your right Metadata screen
            self.text_metadata.setText(report)
            
        except Exception as e:
            self.text_metadata.setText(f"[-] Failed to extract metadata targets: {str(e)}")


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