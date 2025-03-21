import sys
import os
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QTableView, QLabel, QSplitter, 
                            QFileDialog, QPushButton, QMessageBox, QScrollArea, QSizePolicy, QCheckBox)
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, QPoint, QEvent, QRect, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QCursor, QPainter, QColor, QPen

# Debugging helper function
def debug_print(message, level=1):
    """Print debug messages based on verbosity level
    level 0: Always print (errors, critical info)
    level 1: Normal debugging (function calls, basic operations)
    level 2: Verbose debugging (detailed operation info)
    """
    if DikeFinderApp.DEBUG_MODE >= level:
        print(message)

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
            debug_print(f"Attempting to load Excel file: {excel_path}", 1)
            
            # Read Excel file
            df = pd.read_excel(excel_path)
            
            # Remove any unnamed columns or columns we don't need
            df = df[df.columns[~df.columns.str.contains('Unnamed')]]
            
            # Remove the '200 아래' column if it exists
            if '200 아래' in df.columns:
                df = df.drop(columns=['200 아래'])
            
            debug_print(f"Excel file loaded successfully", 1)
            debug_print(f"DataFrame shape after cleanup: {df.shape}", 2)
            debug_print(f"Columns after cleanup: {list(df.columns)}", 2)

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
            
            debug_print(f"Found columns: {existing_columns}", 2)
            debug_print(f"Missing columns: {missing_columns}", 2)
            
            if missing_columns:
                debug_print(f"Warning: Missing columns in Excel file: {missing_columns}", 1)
                debug_print("Will use empty values for missing columns", 1)
                
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
            debug_print(f"Updating model with {len(data_list)} rows of data", 1)
            self.beginResetModel()
            self.data = data_list
            self.endResetModel()
            
            debug_print(f"Successfully loaded {len(data_list)} rows from Excel file", 1)
            return True
            
        except Exception as e:
            debug_print(f"Error loading Excel file: {e}", 0)
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
        
        # Add zoom level label
        self.zoom_level_label = QLabel("100%")
        self.zoom_level_label.setAlignment(Qt.AlignCenter)
        self.zoom_level_label.setStyleSheet("font-size: 10px; min-width: 45px;")
        self.zoom_level_label.setFixedWidth(45)
        
        self.reset_zoom_button = QPushButton("Reset")
        self.reset_zoom_button.setToolTip("Reset Zoom to 100%")
        self.reset_zoom_button.clicked.connect(self.reset_zoom)
        self.reset_zoom_button.setFixedHeight(30)
        
        # Add fit to window button
        self.fit_window_button = QPushButton("Fit")
        self.fit_window_button.setToolTip("Fit Image to Window")
        self.fit_window_button.clicked.connect(self.fit_to_window)
        self.fit_window_button.setFixedHeight(30)
        
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
        top_layout.addWidget(self.zoom_level_label)
        top_layout.addWidget(self.zoom_in_button)
        top_layout.addWidget(self.reset_zoom_button)
        top_layout.addWidget(self.fit_window_button)
        top_layout.addWidget(self.filename_label, 1)  # Give filename label stretch priority
        
        # Create direct image display widget
        self.image_display = ImageDisplayWidget()
        # Connect zoom change signal
        self.image_display.zoom_changed.connect(self.update_zoom_level)
        
        # Add controls and content to the main layout
        self.layout.addLayout(top_layout)
        self.layout.addWidget(self.image_display, 1)  # Give image display stretch priority
        
        # Initialize variables for zooming and panning
        self.image_dir = ""
        self.current_image_path = None
    
    def update_zoom_level(self, scale_factor):
        """Update the zoom level display"""
        percentage = int(scale_factor * 100)
        self.zoom_level_label.setText(f"{percentage}%")
        
    def zoom_in(self):
        """Zoom in by one step"""
        if not self.image_display.original_pixmap:
            return
        
        if self.image_display.scale_factor < self.image_display.max_scale:
            # Adjust zooming in behavior based on current zoom level
            if self.image_display.scale_factor < 0.5:
                # At very low zoom (<50%), use larger increment
                zoom_step = 0.05  # 5% increment
            elif self.image_display.scale_factor < 1.0:
                # At low zoom (50-100%), use moderate increment
                zoom_step = 0.1  # 10% increment
            else:
                # At normal and high zoom (>100%), use exponential scaling
                zoom_step = self.image_display.base_zoom_step * (self.image_display.scale_factor ** 2)
            
            self.image_display.scale_factor = min(self.image_display.scale_factor + zoom_step, self.image_display.max_scale)
            # Emit signal for zoom change
            self.image_display.zoom_changed.emit(self.image_display.scale_factor)
            self.image_display.update()
            
    def zoom_out(self):
        """Zoom out by one step"""
        if not self.image_display.original_pixmap:
            return
        
        if self.image_display.scale_factor > self.image_display.min_scale:
            # For zooming out, use a more gradual approach based on current zoom
            if self.image_display.scale_factor > 5.0:
                # At high zoom levels, use larger steps but not too large
                zoom_step = self.image_display.scale_factor * 0.25  # 25% of current zoom
            elif self.image_display.scale_factor > 2.0:
                # Medium zoom levels
                zoom_step = self.image_display.scale_factor * 0.2  # 20% of current zoom
            elif self.image_display.scale_factor > 0.5:
                # Normal zoom levels
                zoom_step = self.image_display.base_zoom_step
            else:
                # Low zoom levels - smaller steps when already zoomed out
                zoom_step = 0.05
            
            self.image_display.scale_factor = max(self.image_display.scale_factor - zoom_step, self.image_display.min_scale)
            # Emit signal for zoom change
            self.image_display.zoom_changed.emit(self.image_display.scale_factor)
            self.image_display.update()
            
    def reset_zoom(self):
        """Reset zoom to original size"""
        if not self.image_display.original_pixmap:
            return
            
        self.image_display.scale_factor = 1.0
        self.image_display.offset = QPoint(0, 0)
        # Emit signal for zoom change
        self.image_display.zoom_changed.emit(self.image_display.scale_factor)
        self.image_display.update()
        
    def fit_to_window(self):
        """Scale the image to fit within the viewport"""
        if not self.image_display.original_pixmap:
            return
        
        # Calculate the scale factor to fit the image within the viewport
        self.image_display.fit_to_window()
        
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
            debug_print(f"No image found for: {photo_name}", 1)
            return False
        
    def set_image(self, image_path):
        """Load and display an image from the given path"""
        if not os.path.exists(image_path):
            debug_print(f"Image file not found: {image_path}", 0)
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
            debug_print(f"Failed to load image: {image_path}", 0)
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
            debug_print(f"Converting coordinates from cm to pixels: ({x},{y}) cm -> ({x_pixels},{y_pixels}) px", 2)
        else:
            # Already in pixels
            x_pixels = x
            y_pixels = y
            
        # Set marker on display widget (without centering)
        self.image_display.set_marker(int(x_pixels), int(y_pixels))
        # Don't automatically center - we'll do that explicitly after zoom
    
    def clear_marker(self):
        """Clear the marker"""
        self.image_display.clear_marker()


class ImageDisplayWidget(QWidget):
    # Add signal for zoom changes
    zoom_changed = pyqtSignal(float)
    
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
        self.base_zoom_step = 0.1  # Base zoom step at 100%
        
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
        
    def get_adaptive_zoom_step(self):
        """Calculate adaptive zoom step based on current zoom level with asymmetrical behavior"""
        if steps > 0:  # Zooming in
            # For zooming in, use exponential scaling for dramatic effect
            return self.base_zoom_step * (self.scale_factor ** 2)
        else:  # Zooming out
            # For zooming out, use a more gradual approach based on current zoom
            if self.scale_factor > 5.0:
                # At high zoom levels, use larger steps but not too large
                return self.scale_factor * 0.25  # 25% of current zoom
            elif self.scale_factor > 2.0:
                # Medium zoom levels
                return self.scale_factor * 0.2  # 20% of current zoom
            else:
                # Low zoom levels
                return self.base_zoom_step
        
    def load_image(self, image_path):
        """Load an image from file"""
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return False
            
        self.original_pixmap = pixmap
        self.scale_factor = 1.0
        self.offset = QPoint(0, 0)
        self.marker_position = None
        # Emit signal for initial zoom level
        self.zoom_changed.emit(self.scale_factor)
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
        
        # Apply zoom with asymmetric step calculation
        if steps > 0:  # Zooming in
            # Adjust zooming in behavior based on current zoom level
            if self.scale_factor < 0.5:
                # At very low zoom (<50%), use larger increment
                zoom_step = 0.05  # 5% increment
            elif self.scale_factor < 1.0:
                # At low zoom (50-100%), use moderate increment
                zoom_step = 0.1  # 10% increment
            else:
                # At normal and high zoom (>100%), use exponential scaling
                zoom_step = self.base_zoom_step * (self.scale_factor ** 2)
            
            self.scale_factor = min(self.scale_factor + zoom_step, self.max_scale)
        else:  # Zooming out
            # For zooming out, use a more gradual approach based on current zoom
            if self.scale_factor > 5.0:
                # At high zoom levels, use larger steps but not too large
                zoom_step = self.scale_factor * 0.25  # 25% of current zoom
            elif self.scale_factor > 2.0:
                # Medium zoom levels
                zoom_step = self.scale_factor * 0.2  # 20% of current zoom
            elif self.scale_factor > 0.5:
                # Normal zoom levels
                zoom_step = self.base_zoom_step
            else:
                # Low zoom levels - smaller steps when already zoomed out
                zoom_step = 0.05
            
            self.scale_factor = max(self.scale_factor - zoom_step, self.min_scale)
        
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
            
            # Emit signal for zoom change
            self.zoom_changed.emit(self.scale_factor)
            
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
            # Adjust zooming in behavior based on current zoom level
            if self.scale_factor < 0.5:
                # At very low zoom (<50%), use larger increment
                zoom_step = 0.05  # 5% increment
            elif self.scale_factor < 1.0:
                # At low zoom (50-100%), use moderate increment
                zoom_step = 0.1  # 10% increment
        else:
            # At normal and high zoom (>100%), use exponential scaling
            zoom_step = self.base_zoom_step * (self.scale_factor ** 2)
        
        self.scale_factor = min(self.scale_factor + zoom_step, self.max_scale)
        # Emit signal for zoom change
        self.zoom_changed.emit(self.scale_factor)
        self.update()
            
    def zoom_out(self):
        """Zoom out by one step"""
        if not self.original_pixmap:
            return
        
        if self.scale_factor > self.min_scale:
            # For zooming out, use a more gradual approach based on current zoom
            if self.scale_factor > 5.0:
                # At high zoom levels, use larger steps but not too large
                zoom_step = self.scale_factor * 0.25  # 25% of current zoom
            elif self.scale_factor > 2.0:
                # Medium zoom levels
                zoom_step = self.scale_factor * 0.2  # 20% of current zoom
            elif self.scale_factor > 0.5:
                # Normal zoom levels
                zoom_step = self.base_zoom_step
        else:
            # Low zoom levels - smaller steps when already zoomed out
            zoom_step = 0.05
        
        self.scale_factor = max(self.scale_factor - zoom_step, self.min_scale)
        # Emit signal for zoom change
        self.zoom_changed.emit(self.scale_factor)
        self.update()
            
    def reset_zoom(self):
        """Reset zoom to original size"""
        if not self.original_pixmap:
            return
            
        self.scale_factor = 1.0
        self.offset = QPoint(0, 0)
        # Emit signal for zoom change
        self.zoom_changed.emit(self.scale_factor)
        self.update()
        
    def set_marker(self, x, y):
        """Set marker at specified coordinates"""
        debug_print(f"Setting marker at pixel coordinates: ({x}, {y})", 2)
        self.marker_position = QPoint(x, y)
        debug_print(f"Marker position set to: {self.marker_position}", 2)
        # Don't center here - we'll do that explicitly
        self.update()
    
    def clear_marker(self):
        """Clear marker"""
        self.marker_position = None
        self.update()
    
    def center_on_marker(self):
        """Center the view on the marker and ensure it's visible"""
        if not self.marker_position or not self.original_pixmap:
            debug_print("Cannot center: marker or image not available", 1)
            return
        
        # Log initial state
        debug_print(f"Centering on marker: position={self.marker_position}, current offset={self.offset}", 2)
        
        # Calculate offset to center the marker
        center_x = self.width() // 2
        center_y = self.height() // 2
        debug_print(f"Widget center: ({center_x}, {center_y})", 2)
        
        # Get image dimensions
        img_width = self.original_pixmap.width()
        img_height = self.original_pixmap.height()
        debug_print(f"Original image dimensions: {img_width}x{img_height}", 2)
        
        # Calculate the scaled image dimensions and position
        scaled_width = int(img_width * self.scale_factor)
        scaled_height = int(img_height * self.scale_factor)
        debug_print(f"Scaled image dimensions: {scaled_width}x{scaled_height}", 2)
        
        # Calculate image position before offset
        img_x = (self.width() - scaled_width) // 2
        img_y = (self.height() - scaled_height) // 2
        debug_print(f"Image position before offset: ({img_x}, {img_y})", 2)
        
        # Calculate the marker position relative to the viewport
        marker_viewport_x = img_x + int(self.marker_position.x() * self.scale_factor)
        marker_viewport_y = img_y + int(self.marker_position.y() * self.scale_factor)
        debug_print(f"Marker viewport position: ({marker_viewport_x}, {marker_viewport_y})", 2)
        
        # Calculate new offset to center marker in viewport
        new_offset_x = center_x - marker_viewport_x
        new_offset_y = center_y - marker_viewport_y
        debug_print(f"New calculated offset: ({new_offset_x}, {new_offset_y})", 2)
        
        # Apply the offset
        self.offset.setX(new_offset_x)
        self.offset.setY(new_offset_y)
        debug_print(f"Offset updated to: {self.offset}", 2)
        
        # Additional check to ensure marker is visible in viewport
        # Calculate where the marker will be after applying the offset
        final_marker_x = marker_viewport_x + self.offset.x()
        final_marker_y = marker_viewport_y + self.offset.y()
        debug_print(f"Final marker position in viewport: ({final_marker_x}, {final_marker_y})", 2)
        
        # Define visible area margins (add some padding)
        margin = 50
        visible_left = margin
        visible_right = self.width() - margin
        visible_top = margin
        visible_bottom = self.height() - margin
        debug_print(f"Visible area: left={visible_left}, right={visible_right}, top={visible_top}, bottom={visible_bottom}", 2)
        
        # Adjust offset if marker is outside visible area
        if final_marker_x < visible_left:
            self.offset.setX(self.offset.x() + (visible_left - final_marker_x))
            debug_print(f"Adjusted X offset to bring marker into view (left): {self.offset.x()}", 2)
        elif final_marker_x > visible_right:
            self.offset.setX(self.offset.x() - (final_marker_x - visible_right))
            debug_print(f"Adjusted X offset to bring marker into view (right): {self.offset.x()}", 2)
        
        if final_marker_y < visible_top:
            self.offset.setY(self.offset.y() + (visible_top - final_marker_y))
            debug_print(f"Adjusted Y offset to bring marker into view (top): {self.offset.y()}", 2)
        elif final_marker_y > visible_bottom:
            self.offset.setY(self.offset.y() - (final_marker_y - visible_bottom))
            debug_print(f"Adjusted Y offset to bring marker into view (bottom): {self.offset.y()}", 2)
        
        # Final position check
        final_marker_x = marker_viewport_x + self.offset.x()
        final_marker_y = marker_viewport_y + self.offset.y()
        debug_print(f"Final marker position after adjustments: ({final_marker_x}, {final_marker_y})", 2)
        
        self.update()

    def set_zoom_level(self, scale):
        """Set zoom level to the specified scale factor"""
        if not self.original_pixmap:
            return
        
        # Ensure scale is within allowed range
        self.scale_factor = max(min(scale, self.max_scale), self.min_scale)
        # Emit signal for zoom change
        self.zoom_changed.emit(self.scale_factor)
        self.update()

    def fit_to_window(self):
        """Scale the image to fit within the viewport"""
        if not self.original_pixmap:
            return
        
        # Get image dimensions
        img_width = self.original_pixmap.width()
        img_height = self.original_pixmap.height()
        
        # Get viewport dimensions
        view_width = self.width()
        view_height = self.height()
        
        # Calculate scale factors for width and height
        width_scale = view_width / img_width
        height_scale = view_height / img_height
        
        # Use the smaller scale factor to ensure the entire image fits
        # Apply a small margin (0.9) to leave some space around the edges
        scale_factor = min(width_scale, height_scale) * 0.9
        
        debug_print(f"Fitting image to window: scale={scale_factor}", 1)
        
        # Set the new scale factor
        self.scale_factor = scale_factor
        
        # Reset the offset to center the image
        self.offset = QPoint(0, 0)
        
        # Emit signal for zoom change
        self.zoom_changed.emit(self.scale_factor)
        self.update()


class DikeFinderApp(QMainWindow):
    # Class-level debug flag
    DEBUG_MODE = 0  # Default: no debugging (0), Basic (1), Verbose (2)
    
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
        
        # Add center checkbox control
        self.center_checkbox = QCheckBox("Center clicked row")
        self.center_checkbox.setChecked(True)  # Default to checked
        self.center_checkbox.setToolTip("When checked, centers on marker at 200% zoom. When unchecked, fits image to window.")
        button_layout.addWidget(self.center_checkbox)
        
        # Add verbose mode checkbox
        self.verbose_checkbox = QCheckBox("Verbose")
        self.verbose_checkbox.setChecked(False)  # Default to unchecked
        self.verbose_checkbox.setToolTip("Enable verbose debug output")
        self.verbose_checkbox.stateChanged.connect(self.toggle_verbose_mode)
        button_layout.addWidget(self.verbose_checkbox)
        
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

    def toggle_verbose_mode(self, state):
        """Toggle verbose mode on/off"""
        if state == Qt.Checked:
            DikeFinderApp.DEBUG_MODE = 2
            debug_print("Verbose mode enabled", 0)
        else:
            DikeFinderApp.DEBUG_MODE = 0
            debug_print("Verbose mode disabled", 0)

    def set_default_image_directory(self):
        """Set the default image directory to './data'"""
        default_dir = os.path.join(os.getcwd(), "data")
        
        # Create the directory if it doesn't exist
        if not os.path.exists(default_dir):
            try:
                os.makedirs(default_dir)
                debug_print(f"Created default image directory: {default_dir}", 1)
            except Exception as e:
                debug_print(f"Error creating directory: {e}", 0)
                return
        
        # Set the image directory
        self.image_viewer.set_image_dir(default_dir)
        debug_print(f"Default image directory set to: {default_dir}", 1)

    def select_image_directory(self):
        """Open a file dialog to select the directory containing images"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Image Directory", 
            self.image_viewer.image_dir or os.path.expanduser("~"), 
            QFileDialog.ShowDirsOnly
        )
        
        if directory:
            self.image_viewer.set_image_dir(directory)
            debug_print(f"Image directory set to: {directory}", 1)
            # Status bar message instead of popup
            if hasattr(self, 'statusBar'):
                self.statusBar().showMessage(f"Image directory: {directory}", 3000)
    
    def on_row_selected(self, selected, deselected):
        """Handle row selection in the table view"""
        indexes = selected.indexes()
        if indexes:
            # Get the selected row
            row = indexes[0].row()
            debug_print(f"Row {row} selected", 1)
            
            # Get the photo name from the selected row
            photo_name = self.table_model.get_photo_name(row)
            debug_print(f"Photo name: {photo_name}", 1)
            
            # Try to find and display the corresponding image
            if photo_name:
                success = self.image_viewer.set_image_by_name(photo_name)
                if success:
                    # Get the X and Y coordinates from the table (columns 9 and 10)
                    try:
                        x_coord = float(self.table_model.data[row][9])  # 좌표 X
                        y_coord = float(self.table_model.data[row][10])  # 좌표 Y
                        debug_print(f"Coordinates from table: X={x_coord}, Y={y_coord}", 1)
                        
                        # Set marker regardless of centering option
                        self.image_viewer.set_marker(x_coord, y_coord)
                        
                        # Check if we should center on the marker
                        if self.center_checkbox.isChecked():
                            # Center on marker with 200% zoom
                            debug_print("Centering enabled: Setting zoom level to 200%", 1)
                            self.image_viewer.image_display.set_zoom_level(2.0)
                            debug_print("Triggering center on marker", 1)
                            self.image_viewer.image_display.center_on_marker()
                        else:
                            # Fit the image to the window instead of just resetting to 100%
                            debug_print("Centering disabled: Fitting image to window", 1)
                            self.image_viewer.image_display.fit_to_window()
                            
                    except (ValueError, IndexError) as e:
                        debug_print(f"Error setting marker: {e}", 0)
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
            debug_print(f"Data directory not found: {data_dir}", 1)
            return False
        
        # Look for the specific Excel file
        target_file = "석영맥(통합)v1.xlsx"
        excel_path = os.path.join(data_dir, target_file)
        
        if not os.path.exists(excel_path):
            debug_print(f"Target Excel file not found: {excel_path}", 1)
            
            # Fallback to looking for any Excel file
            excel_files = [f for f in os.listdir(data_dir) 
                          if f.lower().endswith(('.xlsx', '.xls'))]
            
            if not excel_files:
                debug_print("No Excel files found in data directory", 1)
                return False
            
            # Use the first Excel file found
            excel_path = os.path.join(data_dir, excel_files[0])
            debug_print(f"Using fallback Excel file: {excel_path}", 1)
        else:
            debug_print(f"Found target Excel file: {excel_path}", 1)
        
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