import sys
import os
from PyQt6 import uic
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget

class SubWindow(QWidget):
    def __init__(self):
        super().__init__()
        # Loads your secondary pop-up design
        uic.loadUi("sub_window.ui", self)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Loads your main dashboard design
        uic.loadUi("workspace.ui", self)
        
        # Keep track of the sub-window instance so Python doesn't delete it
        self.new_window = None
        
        # HOOK YOUR BUTTON HERE:
        # Swap 'btn_open_report' with whatever objectName you gave your button in Designer
        if hasattr(self, "btn_open_report"):
            self.btn_open_report.clicked.connect(self.show_popup)
        else:
            print("[!] Warning: Could not find a button named 'btn_open_report' in workspace.ui")

    def show_popup(self):
        # Create the window if it hasn't been opened yet
        if self.new_window is None:
            self.new_window = SubWindow()
        
        self.new_window.show()
        self.new_window.raise_()
        self.new_window.activateWindow()

if __name__ == "__main__":
    # Check if files exist to avoid messy crashes
    if not os.path.exists("workspace.ui") or not os.path.exists("sub_window.ui"):
        print("[-] Error: Make sure both 'workspace.ui' and 'sub_window.ui' are in this folder!")
        sys.exit(1)

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())