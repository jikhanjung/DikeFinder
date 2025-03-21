import sys
import os
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QTableView, QLabel, QSplitter, 
                            QFileDialog, QPushButton, QMessageBox, QScrollArea)
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
        
        # Create zoom controls
        zoom_layout = QHBoxLayout()
        
        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.setToolTip("Zoom In")
        self.zoom_in_button.clicked.connect(self.zoom_in)
        self.zoom_in_button.setFixedSize(40, 40)
        
        self.zoom_out_button = QPushButton("-")
        self.zoom_out_button.setToolTip("Zoom Out")
        self.zoom_out_button.clicked.connect(self.zoom_out)
        self.zoom_out_button.setFixedSize(40, 40)
        
        self.reset_zoom_button = QPushButton("Reset")
        self.reset_zoom_button.setToolTip("Reset Zoom")
        self.reset_zoom_button.clicked.connect(self.reset_zoom)
        
        zoom_layout.addWidget(self.zoom_out_button)
        zoom_layout.addWidget(self.reset_zoom_button)
        zoom_layout.addWidget(self.zoom_in_button)
        zoom_layout.addStretch()
        
        # Add filename label
        self.filename_label = QLabel("No image loaded")
        self.filename_label.setAlignment(Qt.AlignCenter)
        self.filename_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 5px;")
        
        # Create scroll area for panning
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)  # Changed to False to allow custom sizing
        self.scroll_area.setAlignment(Qt.AlignCenter)
        
        # Create container widget for the image label
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        
        # Image display label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        
        # Set a placeholder image
        self.placeholder = QPixmap(500, 500)
        self.placeholder.fill(Qt.lightGray)
        self.image_label.setPixmap(self.placeholder)
        
        # Add image label to content widget
        self.content_layout.addWidget(self.image_label)
        self.scroll_area.setWidget(self.content_widget)
        
        # Add controls and content to the main layout
        self.layout.addLayout(zoom_layout)
        self.layout.addWidget(self.filename_label)
        self.layout.addWidget(self.scroll_area)
        
        # Initialize variables for zooming and panning
        self.image_dir = ""
        self.current_image_path = None
        self.original_pixmap = None
        self.scale_factor = 1.0
        self.min_scale = 0.1
        self.max_scale = 10.0
        self.zoom_step = 0.1
        
        # Variables for marker overlays
        self.marker_position = None
        self.marker_radius = 20
        self.marker_color = QColor(255, 0, 0, 128)  # Semi-transparent red
        
        # Variables for panning with mouse
        self.panning = False
        self.last_pan_point = QPoint()
        
        # Enable mouse tracking for the image label
        self.image_label.setMouseTracking(True)
        self.image_label.installEventFilter(self)
        
    def eventFilter(self, obj, event):
        """Handle mouse events for panning the image"""
        if obj is self.image_label:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                # Start panning
                self.panning = True
                self.last_pan_point = event.pos()
                self.image_label.setCursor(QCursor(Qt.ClosedHandCursor))
                return True
                
            elif event.type() == QEvent.MouseMove and self.panning:
                # Calculate the difference from the last position
                delta = event.pos() - self.last_pan_point
                self.last_pan_point = event.pos()
                
                # Adjust the scroll bars - allow movement beyond normal bounds
                hbar = self.scroll_area.horizontalScrollBar()
                vbar = self.scroll_area.verticalScrollBar()
                
                # Move the scrollbars
                hbar.setValue(hbar.value() - delta.x())
                vbar.setValue(vbar.value() - delta.y())
                return True
                
            elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton and self.panning:
                # Stop panning
                self.panning = False
                self.image_label.setCursor(QCursor(Qt.OpenHandCursor))
                return True
                
            elif event.type() == QEvent.Wheel:
                # Zoom with mouse wheel centered on cursor position
                degrees = event.angleDelta().y() / 8
                steps = degrees / 15
                
                # Store cursor position for centered zoom
                cursor_pos = event.pos()
                
                old_scale = self.scale_factor
                
                if steps > 0:
                    self.scale_factor = min(self.scale_factor + self.zoom_step, self.max_scale)
                elif steps < 0:
                    self.scale_factor = max(self.scale_factor - self.zoom_step, self.min_scale)
                
                # Only update if scale actually changed
                if old_scale != self.scale_factor:
                    self.zoom_at_position(cursor_pos, old_scale)
                    
                return True
                
            elif event.type() == QEvent.Enter:
                # Change cursor when entering the image area
                if not self.panning:
                    self.image_label.setCursor(QCursor(Qt.OpenHandCursor))
                return True
                
            elif event.type() == QEvent.Leave:
                # Reset cursor when leaving the image area
                self.image_label.setCursor(QCursor(Qt.ArrowCursor))
                return True
                
        return super().eventFilter(obj, event)
        
    def zoom_at_position(self, position, old_scale):
        """Zoom at the specified position, keeping that position fixed under the cursor"""
        if not self.original_pixmap:
            return
            
        # Get scroll bar positions before zoom
        hbar = self.scroll_area.horizontalScrollBar()
        vbar = self.scroll_area.verticalScrollBar()
        
        # Calculate how far the cursor is from the top-left corner of the visible area
        visible_x = position.x() + hbar.value() - self.image_label.x()
        visible_y = position.y() + vbar.value() - self.image_label.y()
        
        # Calculate the relative position within the image
        rel_x = visible_x / (self.original_pixmap.width() * old_scale)
        rel_y = visible_y / (self.original_pixmap.height() * old_scale)
        
        # Update the image with the new scale
        self.update_zoom()
        
        # Calculate the new scroll position to keep the point under the cursor
        # This now works with the larger content area
        new_visible_x = rel_x * (self.original_pixmap.width() * self.scale_factor)
        new_visible_y = rel_y * (self.original_pixmap.height() * self.scale_factor)
        
        # Adjust for the centering offset in the larger content widget
        content_width = self.content_widget.width()
        content_height = self.content_widget.height()
        image_width = self.original_pixmap.width() * self.scale_factor
        image_height = self.original_pixmap.height() * self.scale_factor
        
        x_offset = (content_width - image_width) // 2
        y_offset = (content_height - image_height) // 2
        
        # Set new scroll positions
        hbar.setValue(int(new_visible_x + x_offset - position.x() + self.image_label.x()))
        vbar.setValue(int(new_visible_y + y_offset - position.y() + self.image_label.y()))
        
        print(f"Zoomed at position ({position.x()}, {position.y()}), scale: {self.scale_factor:.2f}")
        
    def zoom_in(self):
        """Increase zoom level by one step"""
        if self.scale_factor < self.max_scale:
            old_scale = self.scale_factor
            self.scale_factor += self.zoom_step
            
            # Get center of viewport for zooming
            viewport = self.scroll_area.viewport()
            center = QPoint(viewport.width() // 2, viewport.height() // 2)
            
            # Zoom at the center of the viewport
            self.zoom_at_position(center, old_scale)
            
    def zoom_out(self):
        """Decrease zoom level by one step"""
        if self.scale_factor > self.min_scale:
            old_scale = self.scale_factor
            self.scale_factor -= self.zoom_step
            
            # Get center of viewport for zooming
            viewport = self.scroll_area.viewport()
            center = QPoint(viewport.width() // 2, viewport.height() // 2)
            
            # Zoom at the center of the viewport
            self.zoom_at_position(center, old_scale)
            
    def reset_zoom(self):
        """Reset zoom to original size"""
        old_scale = self.scale_factor
        self.scale_factor = 1.0
        
        # Get center of viewport for zooming
        viewport = self.scroll_area.viewport()
        center = QPoint(viewport.width() // 2, viewport.height() // 2)
        
        # Zoom at the center of the viewport
        self.zoom_at_position(center, old_scale)
        
    def update_zoom(self):
        """Apply the current zoom level to the image and draw any markers"""
        if self.original_pixmap:
            # Create a new pixmap to draw on
            scaled_size = self.original_pixmap.size() * self.scale_factor
            
            # Start with a clean copy of the original image
            temp_pixmap = self.original_pixmap.scaled(
                scaled_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            # If we have a marker position, draw it
            if self.marker_position is not None:
                # Scale the marker position according to the current zoom
                scaled_x = int(self.marker_position.x() * self.scale_factor)
                scaled_y = int(self.marker_position.y() * self.scale_factor)
                scaled_radius = int(self.marker_radius * self.scale_factor)
                
                # Draw the marker on a copy of the scaled pixmap
                painter = QPainter(temp_pixmap)
                painter.setRenderHint(QPainter.Antialiasing)
                pen = QPen(self.marker_color)
                pen.setWidth(3)
                painter.setPen(pen)
                painter.setBrush(self.marker_color)
                painter.drawEllipse(
                    QPoint(scaled_x, scaled_y),
                    scaled_radius,
                    scaled_radius
                )
                painter.end()
            
            # Set the pixmap with the marker
            self.image_label.setPixmap(temp_pixmap)
            
            # Set the content widget size to be larger than the image to allow panning beyond edges
            viewport_width = self.scroll_area.viewport().width()
            viewport_height = self.scroll_area.viewport().height()
            
            # Make the content area larger than the image by a factor
            # This allows the image to be moved partially out of view
            content_width = max(temp_pixmap.width() * 2, viewport_width * 2)
            content_height = max(temp_pixmap.height() * 2, viewport_height * 2)
            
            # Set the content widget size
            self.content_widget.setFixedSize(content_width, content_height)
            
            # Center the image label in the content widget
            self.image_label.resize(temp_pixmap.size())
            self.image_label.move(
                (content_width - temp_pixmap.width()) // 2,
                (content_height - temp_pixmap.height()) // 2
            )
        
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
            self.set_image(image_path)
            return True
        else:
            print(f"No image found for: {photo_name}")
            return False
        
    def set_image(self, image_path):
        """Load and display an image from the given path"""
        if not os.path.exists(image_path):
            print(f"Image file not found: {image_path}")
            return False
        
        self.current_image_path = image_path
        pixmap = QPixmap(image_path)
        
        if not pixmap.isNull():
            # Store the original pixmap for zooming
            self.original_pixmap = pixmap
            
            # Reset zoom when loading a new image
            self.scale_factor = 1.0
            self.marker_position = None  # Clear any existing marker
            self.update_zoom()
            
            # Update filename label
            filename = os.path.basename(image_path)
            self.filename_label.setText(filename)
            
            return True
        else:
            print(f"Failed to load image: {image_path}")
            self.filename_label.setText("Failed to load image")
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
            
        # Convert to integers for QPoint
        self.marker_position = QPoint(int(x_pixels), int(y_pixels))
        self.update_zoom()  # This will redraw the image with the marker
        
        # Center the view on the marker
        self.center_on_marker()
    
    def center_on_marker(self):
        """Center the view on the current marker"""
        if self.marker_position and self.original_pixmap:
            # Calculate the scaled marker position
            scaled_x = int(self.marker_position.x() * self.scale_factor)
            scaled_y = int(self.marker_position.y() * self.scale_factor)
            
            # Get the viewport size
            viewport_width = self.scroll_area.viewport().width()
            viewport_height = self.scroll_area.viewport().height()
            
            # Calculate the scroll position to center the marker
            hbar = self.scroll_area.horizontalScrollBar()
            vbar = self.scroll_area.verticalScrollBar()
            
            # Adjust for the centering offset in the larger content widget
            content_width = self.content_widget.width()
            content_height = self.content_widget.height()
            image_width = self.original_pixmap.width() * self.scale_factor
            image_height = self.original_pixmap.height() * self.scale_factor
            
            x_offset = (content_width - image_width) // 2
            y_offset = (content_height - image_height) // 2
            
            # Calculate new positions (center the marker in the viewport)
            # Make sure to convert to int for scrollbar setValue method
            new_x = int(max(0, scaled_x + x_offset - viewport_width // 2))
            new_y = int(max(0, scaled_y + y_offset - viewport_height // 2))
            
            # Set the scrollbar positions
            hbar.setValue(new_x)
            vbar.setValue(new_y)
            
            print(f"Centered view on marker at pixel coordinates: ({scaled_x}, {scaled_y})")
    
    def clear_marker(self):
        """Clear the marker"""
        self.marker_position = None
        self.update_zoom()


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