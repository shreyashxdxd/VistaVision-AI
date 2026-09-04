import sys
import os
from PySide6.QtWidgets import QApplication
from frontend.main_window import MainWindow

def main():
    # Set PySide6/Qt platform plugins and library paths if needed on Windows
    # (Qt automatically resolves paths on Windows, but this is a standard boot wrapper)
    app = QApplication(sys.argv)
    app.setStyle('Fusion') # Fusion style is very customizable with QSS
    
    # Initialize the main surveillance desktop software window
    window = MainWindow()
    window.showMaximized() # Launch maximized for premium command-center feel
    
    # Execute application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
