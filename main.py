import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QTableView, QLabel, QSplitter)
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt5.QtGui import QPixmap, QImage

class DykeTableModel(QAbstractTableModel):
    def __init__(self, data=None):
        super().__init__()
        self.headers = ["ID", "Name", "Type", "Location", "Notes"]
        # Sample data - this would be replaced with actual data later
        self.data = data or [
            [1, "Dyke A", "Type 1", "North", "Sample note"],
            [2, "Dyke B", "Type 2", "South", "Another note"],
            [3, "Dyke C", "Type 1", "East", "Third note"],
        ]
    
    def rowCount(self, parent=None):
        return len(self.data)
    
    def columnCount(self, parent=None):
        return len(self.headers)
    
    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return str(self.data[index.row()][index.column()])
        return None
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.headers[section]
        return None


class ImageViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # Image display label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        
        # Set a placeholder image
        self.placeholder = QPixmap(500, 500)
        self.placeholder.fill(Qt.lightGray)
        self.image_label.setPixmap(self.placeholder)
        
        self.layout.addWidget(self.image_label)
        
    def set_image(self, image_path):
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self.image_label.setPixmap(pixmap.scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))
        else:
            print(f"Failed to load image: {image_path}")


class DykeFinderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DykeFinder")
        self.setGeometry(100, 100, 1200, 800)
        
        # Main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Use a splitter for resizable panels
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Create image viewer
        self.image_viewer = ImageViewer()
        
        # Create table view
        self.table_view = QTableView()
        self.table_model = DykeTableModel()
        self.table_view.setModel(self.table_model)
        
        # Adjust table properties
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.setAlternatingRowColors(True)
        
        # Add widgets to splitter
        self.splitter.addWidget(self.image_viewer)
        self.splitter.addWidget(self.table_view)
        
        # Set initial sizes
        self.splitter.setSizes([600, 600])
        
        # Set main layout
        main_layout = QHBoxLayout(self.central_widget)
        main_layout.addWidget(self.splitter)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DykeFinderApp()
    window.show()
    sys.exit(app.exec_()) 