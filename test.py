import sys
import os
from PyQt6 import uic
# Import QDialog alongside QApplication
from PyQt6.QtWidgets import QApplication, QDialog 

# CHANGE QMainWindow to QDialog HERE:
class TestMainWindow(QDialog):
    def __init__(self):
        super().__init__()
        
        print(f"[*] Executing script from directory: {os.getcwd()}")
        print(f"[*] Checking for file: {os.path.abspath('untitled.ui')}")
        
        if not os.path.exists("untitled.ui"):
            print("[-] Error: 'untitled.ui' not found in this folder.")
            return

        try:
            uic.loadUi("untitled.ui", self)
            print("[+] UI loaded successfully!")
        except Exception as e:
            print(f"[-] Crash layout parsing error: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestMainWindow()
    window.show()
    sys.exit(app.exec())