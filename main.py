import sys
import os
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QTableView, QLabel, QSplitter, 
                            QFileDialog, QPushButton, QMessageBox, QScrollArea, QSizePolicy)
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, QPoint, QEvent, QRect
from PyQt5.QtGui import QPixmap, QImage, QCursor, QPainter, QColor, QPen

class DikeTableModel(QAbstractTableModel):
    def __init__(self, data=None):
        super().__init__()
        # Korean column headers from the Excel file
        self.headers = ["지역", "기호", "지층", "대표암상", "시대", "각도", 
                        "거리 (km)", "주소", "색", "좌표 X", "좌표 Y", "사진 이름"]
        
        # Sample data - will be replaced with data from Excel
        self.data = data or [
            ["마전리", "ls", "연천층군 미산층", "석회암", "선캄브리아시대 원생누대", -10.8, 0.26, 
             "경기도 연천군 미산면 아미리 576-3", "하늘색", 30.62, 12.49, "0. 마전리"],
            ["마전리", "ls", "연천층군 미산층", "석회암", "선캄브리아시대 원생누대", -42.3, 0.18, 
             "경기도 연천군 백학면 전동리 산 1", "하늘색", 24.99, 17, "0. 마전리"],
            ["마전리", "ls", "연천층군 미산층", "석회암", "선캄브리아시대 원생누대", -48.1, 0.2, 
             "경기도 연천군 백학면 전동리 산 71", "하늘색", 20.01, 17.56, "0. 마전리"],
            ["오호", "Krhd", "유문암맥", "유문암맥", "중생대 백악기", -2.1, 0.19, 
             "강원특별자치도 고성군 죽왕면 가진리 산 59", "빨간색", 1.15, 17.02, "1. 오호"],
            ["만대리", "Kad", "유문암, 규장암", "산성암맥 유문암, 규장암", "중생대 백악기", -87.7, 0.36, 
             "강원특별자치도 인제군 서화면 서흥리 851-4", "빨간색", 32.11, 19.42, "3. 만대리"],
            ["만대리", "Kad", "유문암, 규장암", "산성암맥 유문암, 규장암", "중생대 백악기", -68.9, 0.39, 
             "강원특별자치도 양구군 동면 팔랑리 산 10-4", "빨간색", 13.57, 14.05, "3. 만대리"]
        ]
    
    def load_data_from_excel(self, excel_path):
        """Load data from Excel file and update the model"""
        try:
            print(f"Attempting to load Excel file: {excel_path}")
            
            # Read Excel file
            df = pd.read_excel(excel_path)
            
            # Remove any unnamed columns or columns we don't need
            df = df[df.columns[~df.columns.str.contains('Unnamed')]]
            
            # Remove the '200 아래' column if it exists
            if '200 아래' in df.columns:
                df = df.drop(columns=['200 아래'])
            
            print(f"Excel file loaded successfully")
            print(f"DataFrame shape after cleanup: {df.shape}")
            print(f"Columns after cleanup: {list(df.columns)}")

            # Check if necessary columns exist
            required_columns = self.headers
            
            # Check which columns actually exist
            existing_columns = []
            missing_columns = []
            for col in required_columns:
                if col in df.columns:
                    existing_columns.append(col)
                else:
                    missing_columns.append(col)
            
            print(f"Found columns: {existing_columns}")
            print(f"Missing columns: {missing_columns}")
            
            if missing_columns:
                print(f"Warning: Missing columns in Excel file: {missing_columns}")
                print("Will use empty values for missing columns")
                
            # Convert DataFrame to list of lists (only keeping required columns that exist)
            data_list = []
            for _, row in df.iterrows():
                data_row = []
                for col in required_columns:
                    if col in df.columns:
                        data_row.append(row[col])
                    else:
                        # Add empty value for missing columns
                        data_row.append("")
                data_list.append(data_row)
            
            # Update model data
            print(f"Updating model with {len(data_list)} rows of data")
            self.beginResetModel()
            self.data = data_list
            self.endResetModel()
            
            print(f"Successfully loaded {len(data_list)} rows from Excel file")
            return True
            
        except Exception as e:
            print(f"Error loading Excel file: {e}")
            import traceback
            traceback.print_exc()
            return False
    
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
    
    def get_photo_name(self, row):
        """Return the photo name for the given row"""
        if 0 <= row < len(self.data):
            return self.data[row][11]  # 11 is the index of "사진 이름"
        return None


class ImageViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create top control bar with zoom buttons and filename
        top_layout = QHBoxLayout()
        
        # Create zoom controls
        self.zoom_out_button = QPushButton("-")
        self.zoom_out_button.setToolTip("Zoom Out")
        self.zoom_out_button.clicked.connect(self.zoom_out)
        self.zoom_out_button.setFixedSize(30, 30)
        
        self.reset_zoom_button = QPushButton("Reset")
        self.reset_zoom_button.setToolTip("Reset Zoom")
        self.reset_zoom_button.clicked.connect(self.reset_zoom)
        self.reset_zoom_button.setFixedHeight(30)
        
        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.setToolTip("Zoom In")
        self.zoom_in_button.clicked.connect(self.zoom_in)
        self.zoom_in_button.setFixedSize(30, 30)
        
        # Add filename label with ellipsis for long names
        self.filename_label = QLabel("No image loaded")
        self.filename_label.setAlignment(Qt.AlignCenter)
        self.filename_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        # Set size policy to allow the label to shrink
        self.filename_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        # Enable text elision for long filenames
        self.filename_label.setTextFormat(Qt.PlainText)
        self.filename_label.setWordWrap(False)
        
        # Add widgets to top layout
        top_layout.addWidget(self.zoom_out_button)
        top_layout.addWidget(self.reset_zoom_button)
        top_layout.addWidget(self.zoom_in_button)
        top_layout.addWidget(self.filename_label, 1)  # Give filename label stretch priority
        
        # Create direct image display widget
        self.image_display = ImageDisplayWidget()
        
        # Add controls and content to the main layout
        self.layout.addLayout(top_layout)
        self.layout.addWidget(self.image_display, 1)  # Give image display stretch priority
        
        # Initialize variables for zooming and panning
        self.image_dir = ""
        self.current_image_path = None
        
    def zoom_in(self):
        """Increase zoom level by one step"""
        self.image_display.zoom_in()
            
    def zoom_out(self):
        """Decrease zoom level by one step"""
        self.image_display.zoom_out()
            
    def reset_zoom(self):
        """Reset zoom to original size"""
        self.image_display.reset_zoom()
        
    def set_image_dir(self, directory):
        """Set the directory where images are stored"""
        self.image_dir = directory
        
    def find_image_file(self, photo_name):
        """Find an image file containing the photo_name in its filename"""
        if not self.image_dir or not os.path.exists(self.image_dir):
            return None
            
        for filename in os.listdir(self.image_dir):
            if photo_name in filename and filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                return os.path.join(self.image_dir, filename)
        
        return None
        
    def set_image_by_name(self, photo_name):
        """Find and set an image that contains the photo_name in its filename"""
        if not photo_name:
            return False
            
        image_path = self.find_image_file(photo_name)
        if image_path:
            success = self.set_image(image_path)
            return success
        else:
            print(f"No image found for: {photo_name}")
            return False
        
    def set_image(self, image_path):
        """Load and display an image from the given path"""
        if not os.path.exists(image_path):
            print(f"Image file not found: {image_path}")
            return False
        
        self.current_image_path = image_path
        success = self.image_display.load_image(image_path)
        
        if success:
            # Update filename label with ellipsis for long names
            filename = os.path.basename(image_path)
            self.filename_label.setText(filename)
            # Ensure the label shows ellipsis for long text
            self.filename_label.setToolTip(filename)  # Show full name on hover
            return True
        else:
            print(f"Failed to load image: {image_path}")
            self.filename_label.setText("Failed to load image")
            self.filename_label.setToolTip("")
            return False

    def set_marker(self, x, y):
        """Set a marker at the specified coordinates and update the display"""
        # Check if coordinates are floats (centimeters) or integers (pixels)
        if isinstance(x, float) or isinstance(y, float):
            # Convert from centimeters to pixels (assuming 96 DPI)
            # 1 inch = 2.54 cm, and 96 pixels = 1 inch
            # So 1 cm = 96/2.54 ≈ 37.8 pixels
            pixels_per_cm = 96 / 2.54
            x_pixels = x * pixels_per_cm
            y_pixels = y * pixels_per_cm
            print(f"Converting coordinates from cm to pixels: ({x},{y}) cm -> ({x_pixels},{y_pixels}) px")
        else:
            # Already in pixels
            x_pixels = x
            y_pixels = y
            
        # Set marker on display widget
        self.image_display.set_marker(int(x_pixels), int(y_pixels))
    
    def clear_marker(self):
        """Clear the marker"""
        self.image_display.clear_marker()


class ImageDisplayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set focus policy to receive keyboard events
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        
        # Variables for image display
        self.original_pixmap = None
        self.displayed_pixmap = None
        
        # Variables for zooming
        self.scale_factor = 1.0
        self.min_scale = 0.1
        self.max_scale = 10.0
        self.zoom_step = 0.1
        
        # Variables for panning
        self.panning = False
        self.last_pan_point = QPoint()
        self.offset = QPoint(0, 0)
        
        # Variables for marker
        self.marker_position = None
        self.marker_radius = 20
        self.marker_color = QColor(255, 0, 0, 128)  # Semi-transparent red
        
        # Set a placeholder background
        self.setMinimumSize(500, 500)
        self.placeholder_color = Qt.lightGray
        
    def load_image(self, image_path):
        """Load an image from file"""
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return False
            
        self.original_pixmap = pixmap
        self.scale_factor = 1.0
        self.offset = QPoint(0, 0)
        self.marker_position = None
        self.update()
        return True
        
    def paintEvent(self, event):
        """Draw the image with current zoom and pan settings"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Fill the background
        painter.fillRect(self.rect(), self.placeholder_color)
        
        if self.original_pixmap:
            # Calculate scaled image size
            scaled_size = self.original_pixmap.size() * self.scale_factor
            scaled_pixmap = self.original_pixmap.scaled(
                scaled_size.width(),
                scaled_size.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            # Calculate position to center the image in the viewport and apply offset
            x = (self.width() - scaled_pixmap.width()) // 2 + self.offset.x()
            y = (self.height() - scaled_pixmap.height()) // 2 + self.offset.y()
            
            # Draw the scaled image at the offset position
            painter.drawPixmap(x, y, scaled_pixmap)
            
            # Draw marker if present
            if self.marker_position:
                # Calculate marker position with zoom and pan
                marker_x = x + int(self.marker_position.x() * self.scale_factor)
                marker_y = y + int(self.marker_position.y() * self.scale_factor)
                scaled_radius = int(self.marker_radius * self.scale_factor)
                
                # Draw marker
                painter.setPen(QPen(self.marker_color, 3))
                painter.setBrush(self.marker_color)
                painter.drawEllipse(
                    QPoint(marker_x, marker_y),
                    scaled_radius,
                    scaled_radius
                )
        
    def wheelEvent(self, event):
        """Handle mouse wheel for zooming"""
        if not self.original_pixmap:
            return
            
        # Get mouse position
        mouse_pos = event.pos()
        
        # Calculate zoom change
        degrees = event.angleDelta().y() / 8
        steps = degrees / 15
        
        old_scale = self.scale_factor
        
        # Apply zoom
        if steps > 0:
            self.scale_factor = min(self.scale_factor + self.zoom_step, self.max_scale)
        elif steps < 0:
            self.scale_factor = max(self.scale_factor - self.zoom_step, self.min_scale)
        
        # Only update if scale changed
        if old_scale != self.scale_factor:
            # Calculate position relative to image center
            center_x = self.width() // 2 + self.offset.x()
            center_y = self.height() // 2 + self.offset.y()
            
            # Calculate mouse offset from center
            rel_x = mouse_pos.x() - center_x
            rel_y = mouse_pos.y() - center_y
            
            # Adjust offset to keep point under cursor
            self.offset.setX(self.offset.x() - int(rel_x * (self.scale_factor / old_scale - 1)))
            self.offset.setY(self.offset.y() - int(rel_y * (self.scale_factor / old_scale - 1)))
            
            # Redraw
            self.update()
            
    def mousePressEvent(self, event):
        """Handle mouse press for panning"""
        if event.button() == Qt.LeftButton:
            self.panning = True
            self.last_pan_point = event.pos()
            self.setCursor(QCursor(Qt.ClosedHandCursor))
            
    def mouseMoveEvent(self, event):
        """Handle mouse movement for panning"""
        if self.panning:
            # Calculate the movement delta
            delta = event.pos() - self.last_pan_point
            self.last_pan_point = event.pos()
            
            # Update offset
            self.offset += delta
            
            # Redraw
            self.update()
        else:
            # Change cursor when not panning
            if self.original_pixmap:
                self.setCursor(QCursor(Qt.OpenHandCursor))
            
    def mouseReleaseEvent(self, event):
        """Handle mouse release for panning"""
        if event.button() == Qt.LeftButton and self.panning:
            self.panning = False
            self.setCursor(QCursor(Qt.OpenHandCursor))
            
    def zoom_in(self):
        """Zoom in by one step"""
        if not self.original_pixmap:
            return
            
        if self.scale_factor < self.max_scale:
            self.scale_factor += self.zoom_step
            self.update()
            
    def zoom_out(self):
        """Zoom out by one step"""
        if not self.original_pixmap:
            return
            
        if self.scale_factor > self.min_scale:
            self.scale_factor -= self.zoom_step
            self.update()
            
    def reset_zoom(self):
        """Reset zoom to original size"""
        if not self.original_pixmap:
            return
            
        self.scale_factor = 1.0
        self.offset = QPoint(0, 0)
        self.update()
        
    def set_marker(self, x, y):
        """Set marker at specified coordinates"""
        self.marker_position = QPoint(x, y)
        self.center_on_marker()
        self.update()
    
    def clear_marker(self):
        """Clear marker"""
        self.marker_position = None
        self.update()
        
    def center_on_marker(self):
        """Center the view on the marker"""
        if not self.marker_position or not self.original_pixmap:
            return
            
        # Reset offset to center the marker
        self.offset = QPoint(0, 0)
        self.update()


class DikeFinderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DikeFinder")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create status bar
        self.statusBar().showMessage("Application started")
        
        # Main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(self.central_widget)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        # Add load image directory button
        self.load_dir_button = QPushButton("Set Image Directory")
        self.load_dir_button.clicked.connect(self.select_image_directory)
        button_layout.addWidget(self.load_dir_button)
        
        # Add load Excel data button
        self.load_excel_button = QPushButton("Load Excel Data")
        self.load_excel_button.clicked.connect(self.load_excel_data)
        button_layout.addWidget(self.load_excel_button)
        
        # Add the button layout to the main layout
        main_layout.addLayout(button_layout)
        
        # Use a splitter for resizable panels
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Create image viewer
        self.image_viewer = ImageViewer()
        
        # Create table view
        self.table_view = QTableView()
        self.table_model = DikeTableModel()
        self.table_view.setModel(self.table_model)
        
        # Adjust table properties
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(True)
        
        # Connect table selection to image loading
        self.table_view.selectionModel().selectionChanged.connect(self.on_row_selected)
        
        # Add widgets to splitter
        self.splitter.addWidget(self.image_viewer)
        self.splitter.addWidget(self.table_view)
        
        # Set initial sizes
        self.splitter.setSizes([600, 600])
        
        # Add splitter to main layout
        main_layout.addWidget(self.splitter)

        # Set default image directory to './data'
        self.set_default_image_directory()
        
        # Try to find and load Excel file from data directory
        self.load_excel_from_data_dir()

    def set_default_image_directory(self):
        """Set the default image directory to './data'"""
        default_dir = os.path.join(os.getcwd(), "data")
        
        # Create the directory if it doesn't exist
        if not os.path.exists(default_dir):
            try:
                os.makedirs(default_dir)
                print(f"Created default image directory: {default_dir}")
            except Exception as e:
                print(f"Error creating directory: {e}")
                return
        
        # Set the image directory
        self.image_viewer.set_image_dir(default_dir)
        print(f"Default image directory set to: {default_dir}")

    def select_image_directory(self):
        """Open a file dialog to select the directory containing images"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Image Directory", 
            self.image_viewer.image_dir or os.path.expanduser("~"), 
            QFileDialog.ShowDirsOnly
        )
        
        if directory:
            self.image_viewer.set_image_dir(directory)
            print(f"Image directory set to: {directory}")
            # Status bar message instead of popup
            if hasattr(self, 'statusBar'):
                self.statusBar().showMessage(f"Image directory: {directory}", 3000)
    
    def on_row_selected(self, selected, deselected):
        """Handle row selection in the table view"""
        indexes = selected.indexes()
        if indexes:
            # Get the selected row
            row = indexes[0].row()
            
            # Get the photo name from the selected row
            photo_name = self.table_model.get_photo_name(row)
            
            # Try to find and display the corresponding image
            if photo_name:
                success = self.image_viewer.set_image_by_name(photo_name)
                if success:
                    # Get the X and Y coordinates from the table (columns 9 and 10)
                    try:
                        x_coord = float(self.table_model.data[row][9])  # 좌표 X
                        y_coord = float(self.table_model.data[row][10])  # 좌표 Y
                        
                        # Draw a marker at these coordinates
                        self.image_viewer.set_marker(x_coord, y_coord)
                        print(f"Marked coordinates: X={x_coord}, Y={y_coord}")
                    except (ValueError, IndexError) as e:
                        print(f"Error setting marker: {e}")
                elif self.image_viewer.image_dir:
                    QMessageBox.warning(
                        self, 
                        "Image Not Found", 
                        f"Could not find an image file containing '{photo_name}' in the selected directory."
                    )

    def load_excel_from_data_dir(self):
        """Find and load Excel file from the data directory"""
        data_dir = os.path.join(os.getcwd(), "data")
        
        if not os.path.exists(data_dir):
            print(f"Data directory not found: {data_dir}")
            return False
        
        # Look for the specific Excel file
        target_file = "석영맥(통합)v1.xlsx"
        excel_path = os.path.join(data_dir, target_file)
        
        if not os.path.exists(excel_path):
            print(f"Target Excel file not found: {excel_path}")
            
            # Fallback to looking for any Excel file
            excel_files = [f for f in os.listdir(data_dir) 
                          if f.lower().endswith(('.xlsx', '.xls'))]
            
            if not excel_files:
                print("No Excel files found in data directory")
                return False
            
            # Use the first Excel file found
            excel_path = os.path.join(data_dir, excel_files[0])
            print(f"Using fallback Excel file: {excel_path}")
        else:
            print(f"Found target Excel file: {excel_path}")
        
        # Load the data from the Excel file
        success = self.table_model.load_data_from_excel(excel_path)
        
        if success:
            filename = os.path.basename(excel_path)
            self.statusBar().showMessage(f"Loaded data from {filename}", 5000)
        
        return success
    
    def load_excel_data(self):
        """Open a file dialog to select an Excel file"""
        file_filter = "Excel Files (*.xlsx *.xls);;All Files (*)"
        excel_path, _ = QFileDialog.getOpenFileName(
            self, "Select Excel File", 
            self.image_viewer.image_dir or os.path.expanduser("~"), 
            file_filter
        )
        
        if excel_path:
            success = self.table_model.load_data_from_excel(excel_path)
            
            if success:
                self.statusBar().showMessage(f"Loaded data from {os.path.basename(excel_path)}", 5000)
            else:
                QMessageBox.warning(
                    self, 
                    "Error Loading Excel",
                    f"Failed to load data from the selected Excel file."
                )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DikeFinderApp()
    window.show()
    sys.exit(app.exec_()) 


''' 
How to make an exe file

pyinstaller --name "DikeFinder_v0.0.1.exe" --onefile --noconsole main.py
pyinstaller --onedir --noconsole --add-data "icons/*.png;icons" --add-data "translations/*.qm;translations" --add-data "migrations/*;migrations" --icon="icons/Modan2_2.png" --noconfirm Modan2.py
#--upx-dir=/path/to/upx

for MacOS
pyinstaller --onefile --noconsole --add-data "icons/*.png:icons" --add-data "translations/*.qm:translations" --add-data "migrations/*:migrations" --icon="icons/Modan2_2.png" Modan2.py
pyinstaller --onedir --noconsole --add-data "icons/*.png:icons" --add-data "translations/*.qm:translations" --add-data "migrations/*:migrations" --icon="icons/Modan2_2.png" --noconfirm Modan2.py

pylupdate5 Modan2.py ModanComponents.py ModanDialogs.py -ts translations/Modan2_en.ts
pylupdate5 Modan2.py ModanComponents.py ModanDialogs.py -ts translations/Modan2_ko.ts
pylupdate5 Modan2.py ModanComponents.py ModanDialogs.py -ts translations/Modan2_ja.ts

linguist


'''