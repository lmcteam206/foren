import os
from PyQt6 import uic
from PyQt6.QtWidgets import QDialog, QPushButton

class CalculatorDialog(QDialog):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        # Safely acquire the path layout matching the running file directory location
        plugin_dir = os.path.dirname(__file__)
        uic.loadUi(os.path.join(plugin_dir, "calculator.ui"), self)
        
        self.expression = ""
        
        # Link functional number grid mapping loops
        buttons = [
            self.btn_0, self.btn_1, self.btn_2, self.btn_3, self.btn_4,
            self.btn_5, self.btn_6, self.btn_7, self.btn_8, self.btn_9,
            self.btn_add, self.btn_sub, self.btn_mul, self.btn_div, self.btn_dot
        ]
        
        for btn in buttons:
            btn.clicked.connect(self.append_character)
            
        self.btn_clear.clicked.connect(self.clear_display)
        self.btn_equal.clicked.connect(self.calculate_expression)

    def append_character(self):
        sender_button = self.sender()
        if isinstance(sender_button, QPushButton):
            self.expression += sender_button.text()
            self.display.setText(self.expression)

    def clear_display(self):
        self.expression = ""
        self.display.clear()

    def calculate_expression(self):
        try:
            # Parse math strings safely through native math handling logic entries
            result = str(eval(self.expression))
            self.display.setText(result)
            self.expression = result # Feed current outcome straight back to anchor tracking memory
        except Exception:
            self.display.setText("Error")
            self.expression = ""

def main_run(parent_window):
    """Core structural dynamic loading execution hook required by main_window engine."""
    dialog = CalculatorDialog(parent_window)
    dialog.exec()