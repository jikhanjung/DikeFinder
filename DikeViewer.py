import sys
import os
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QTableView, QLabel, QSplitter, 
                            QFileDialog, QPushButton, QMessageBox, QScrollArea, QSizePolicy, QCheckBox, QLayout, QLineEdit, QTableWidget, QTableWidgetItem,
                            QHeaderView)
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, QPoint, QEvent, QRect, pyqtSignal, QSortFilterProxyModel, QSize, QUrl, QObject, QTimer, QSettings
from PyQt5.QtGui import QPixmap, QImage, QCursor, QPainter, QColor, QPen
from PyQt5.QtWebChannel import QWebChannel
import json
import csv
import re

# Try to import WebEngine components, but continue even if they're not available
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
    WEB_ENGINE_AVAILABLE = True
except ImportError:
    WEB_ENGINE_AVAILABLE = False
    print("PyQt5.QtWebEngineWidgets not found. KIGAM map feature will be disabled.")
    print("To enable this feature, install it with: pip install PyQtWebEngine")

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
        # Add sequence number as first column, followed by Korean column headers
        self.headers = ["#", "지역", "기호", "지층", "대표암상", "시대", "각도", 
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
            # Skip the first column (sequence number) as it's generated
            required_columns = self.headers[1:]
            
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
                debug_print(f"Data row: {data_row}", 2)
            
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
        if index.column() == 0:  # Sequence number column
            if role == Qt.DisplayRole:
                # Return as string for display
                return str(index.row() + 1)
            elif role == Qt.UserRole:
                # Return as integer for sorting
                return index.row() + 1
        else:
            if role == Qt.DisplayRole:
                # For all other columns, return data from the model
                return str(self.data[index.row()][index.column() - 1])
            elif role == Qt.UserRole:
                # For other columns, provide the same data for sorting
                return self.data[index.row()][index.column() - 1]
        return None
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.headers[section]
        return None
    
    def get_photo_name(self, row):
        """Return the photo name for the given row"""
        if 0 <= row < len(self.data):
            return self.data[row][11]  # Still index 11 in the data array (12th column in display)
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

    def set_multiple_markers(self, coordinates_list, primary_index=None, sequence_numbers=None):
        """Set multiple markers from a list of coordinates
        
        Args:
            coordinates_list: List of (x, y) coordinate pairs
            primary_index: Index of the primary marker (if any)
            sequence_numbers: List of sequence numbers for the markers
        """
        # Convert all coordinates to pixel positions
        markers = []
        primary_marker = None
        marker_numbers = []
        primary_number = None
        
        pixels_per_cm = 96 / 2.54  # Convert cm to pixels
        
        for i, (x, y) in enumerate(coordinates_list):
            # Convert to pixels if needed
            if isinstance(x, float) or isinstance(y, float):
                x_pixels = x * pixels_per_cm
                y_pixels = y * pixels_per_cm
            else:
                x_pixels = x
                y_pixels = y
            
            point = QPoint(int(x_pixels), int(y_pixels))
            
            # Set as primary marker if it matches the primary index
            if i == primary_index:
                primary_marker = point
                if sequence_numbers and i < len(sequence_numbers):
                    primary_number = sequence_numbers[i]
            else:
                markers.append(point)
                if sequence_numbers and i < len(sequence_numbers):
                    marker_numbers.append(sequence_numbers[i])
        
        # Set markers
        self.image_display.set_multiple_markers(markers, primary_marker, marker_numbers, primary_number)


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
        
        # Variables for markers
        self.marker_position = None  # Primary marker
        self.secondary_markers = []  # Additional markers
        self.marker_numbers = []     # Sequence numbers for markers
        self.marker_radius = 20
        self.marker_color = QColor(255, 0, 0, 128)  # Semi-transparent red
        
        # Set a placeholder background
        self.setMinimumSize(500, 500)
        self.placeholder_color = Qt.lightGray
        
    def get_adaptive_zoom_step(self, steps):
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
            
            # Draw secondary markers first (smaller and dimmer)
            if hasattr(self, 'secondary_markers') and self.secondary_markers:
                # Use a more transparent color for secondary markers
                secondary_color = QColor(255, 0, 0, 60)  # Very transparent red
                #painter.setPen(QPen(secondary_color, 2))
                painter.setPen(QPen(Qt.white, 2))
                painter.setBrush(secondary_color)
                
                for i, marker_pos in enumerate(self.secondary_markers):
                    if marker_pos:
                        # Calculate marker position with zoom and pan
                        marker_x = x + int(marker_pos.x() * self.scale_factor)
                        marker_y = y + int(marker_pos.y() * self.scale_factor)
                        
                        # Use a smaller radius for secondary markers
                        scaled_radius = int(self.marker_radius * 0.6 * self.scale_factor)
                        
                        # Draw smaller marker
                        painter.drawEllipse(
                            QPoint(marker_x, marker_y),
                            scaled_radius,
                            scaled_radius
                        )
                        
                        # Draw sequence number on marker if available
                        if hasattr(self, 'marker_numbers') and i < len(self.marker_numbers):
                            painter.setPen(QPen(Qt.white, 2))
                            # Set font for number
                            font = painter.font()
                            font.setBold(True)
                            scaled_font_size = max(8, int(9 * self.scale_factor))
                            font.setPointSize(scaled_font_size)
                            painter.setFont(font)
                            
                            # Draw number centered in marker
                            text_rect = QRect(
                                marker_x - scaled_radius, 
                                marker_y - scaled_radius,
                                scaled_radius * 2, 
                                scaled_radius * 2
                            )
                            painter.drawText(text_rect, Qt.AlignCenter, str(self.marker_numbers[i]))
            
            # Draw primary marker if present (larger and more visible)
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
                
                # Draw sequence number on primary marker if available
                if hasattr(self, 'primary_marker_number') and self.primary_marker_number is not None:
                    painter.setPen(QPen(Qt.white, 2))
                    # Set font for number
                    font = painter.font()
                    font.setBold(True)
                    scaled_font_size = max(10, int(12 * self.scale_factor))
                    font.setPointSize(scaled_font_size)
                    painter.setFont(font)
                    
                    # Draw number centered in marker
                    text_rect = QRect(
                        marker_x - scaled_radius, 
                        marker_y - scaled_radius,
                        scaled_radius * 2, 
                        scaled_radius * 2
                    )
                    painter.drawText(text_rect, Qt.AlignCenter, str(self.primary_marker_number))
        
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
        """Clear all markers"""
        self.marker_position = None
        self.secondary_markers = []
        self.marker_numbers = []
        self.primary_marker_number = None
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

    def set_multiple_markers(self, markers, primary_marker=None, marker_numbers=None, primary_number=None):
        """Set multiple markers at specified coordinates with sequence numbers
        
        Args:
            markers: List of (x, y) tuples for marker positions
            primary_marker: Optional (x, y) tuple for the primary marker position
            marker_numbers: List of sequence numbers for markers
            primary_number: Sequence number for primary marker
        """
        debug_print(f"Setting {len(markers)} markers", 2)
        
        # Clear existing markers
        self.marker_position = primary_marker  # Keep the primary marker for traditional functionality
        self.secondary_markers = markers if markers else []  # Add secondary markers
        
        # Store sequence numbers
        self.marker_numbers = marker_numbers if marker_numbers else []
        self.primary_marker_number = primary_number
        
        # Update the display
        self.update()


class FlowLayout(QLayout):
    """Custom flow layout that automatically arranges widgets in multiple rows based on available space"""
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items = []
        
    def __del__(self):
        while self.count():
            item = self.takeAt(0)
            del item
        
    def addItem(self, item):
        self._items.append(item)
        
    def count(self):
        return len(self._items)
        
    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None
        
    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None
        
    def expandingDirections(self):
        return Qt.Orientations(0)
        
    def hasHeightForWidth(self):
        return True
        
    def heightForWidth(self, width):
        return self._doLayout(QRect(0, 0, width, 0), True)
        
    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._doLayout(rect, False)
        
    def sizeHint(self):
        width = self.minimumSize().width()
        height = self.heightForWidth(width)
        return QSize(width, height)
        
    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        
        margin = self.contentsMargins()
        size += QSize(2 * margin.left(), 2 * margin.top())
        return size
        
    def _doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0
        
        for item in self._items:
            wid = item.widget()
            spaceX = self.spacing() + wid.style().layoutSpacing(
                QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Horizontal)
            spaceY = self.spacing() + wid.style().layoutSpacing(
                QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Vertical)
            
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0
                
            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
                
            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())
            
        return y + lineHeight - rect.y()


# Define the KIGAMMapWindow class only if WebEngine is available
if WEB_ENGINE_AVAILABLE:
    class KIGAMMapWindow(QMainWindow):
        """A window to display the geological map from KIGAM website"""
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("KIGAM Geological Map")
            self.setGeometry(200, 200, 1000, 800)
            
            # Create central widget and layout
            self.central_widget = QWidget()
            self.setCentralWidget(self.central_widget)
            self.layout = QVBoxLayout(self.central_widget)
            
            # Settings for credential storage
            self.settings = QSettings("DikeFinder", "KIGAMMap")
            
            # Add login controls
            login_layout = QHBoxLayout()
            
            self.email_label = QLabel("Email:")
            self.email_input = QLineEdit()
            self.password_label = QLabel("Password:")
            self.password_input = QLineEdit()
            self.password_input.setEchoMode(QLineEdit.Password)
            self.remember_me = QCheckBox("Remember Me")
            self.login_button = QPushButton("Login")
            self.login_button.clicked.connect(self.login_to_kigam)
            self.clear_credentials_button = QPushButton("Clear Saved")
            self.clear_credentials_button.clicked.connect(self.clear_saved_credentials)
            self.clear_credentials_button.setToolTip("Clear saved credentials")
            
            login_layout.addWidget(self.email_label)
            login_layout.addWidget(self.email_input)
            login_layout.addWidget(self.password_label)
            login_layout.addWidget(self.password_input)
            login_layout.addWidget(self.remember_me)
            login_layout.addWidget(self.login_button)
            login_layout.addWidget(self.clear_credentials_button)
            
            self.layout.addLayout(login_layout)
            
            # Add login status label
            self.login_status = QLabel("")
            self.login_status.setStyleSheet("color: blue;")
            self.layout.addWidget(self.login_status)
            
            # Add map tool controls
            tools_layout = QHBoxLayout()
            
            self.info_button = QPushButton("Info Tool")
            self.info_button.setToolTip("Activate the information tool and click on the map to see geological data")
            self.info_button.clicked.connect(self.activate_info_tool)
            self.info_button.setCheckable(True)
            
            self.add_to_table_button = QPushButton("Add to Table")
            self.add_to_table_button.setToolTip("Add current geological information to the table")
            self.add_to_table_button.clicked.connect(self.add_current_info_to_table)
            self.add_to_table_button.setEnabled(False)  # Disabled until we have info
            
            # Add info display as a QLineEdit instead of a large text box
            self.info_label = QLineEdit()
            self.info_label.setReadOnly(True)
            self.info_label.setPlaceholderText("Geological information will appear here")
            self.info_label.setMinimumWidth(400)
            
            # Add coordinate display
            self.coords_label = QLabel("Coordinates: ")
            
            tools_layout.addWidget(self.info_button)
            tools_layout.addWidget(self.info_label)
            tools_layout.addWidget(self.coords_label)
            tools_layout.addWidget(self.add_to_table_button)
            tools_layout.addStretch(1)  # Add stretch to push other widgets to the right
            
            self.layout.addLayout(tools_layout)
            
            # Create web view
            self.web_view = QWebEngineView()
            self.web_view.loadFinished.connect(self.on_page_load_finished)
            self.web_view.setMinimumHeight(500)
            
            # Create splitter for map and table
            self.splitter = QSplitter(Qt.Vertical)
            self.layout.addWidget(self.splitter, 1)  # Give splitter stretch priority
            
            # Add web view to top part of splitter
            self.web_view_container = QWidget()
            self.web_view_layout = QVBoxLayout(self.web_view_container)
            self.web_view_layout.setContentsMargins(0, 0, 0, 0)
            self.web_view_layout.addWidget(self.web_view)
            self.splitter.addWidget(self.web_view_container)
            
            # Create table view in bottom part of splitter
            self.table_container = QWidget()
            self.table_layout = QVBoxLayout(self.table_container)
            
            # Add table controls
            table_controls_layout = QHBoxLayout()
            
            self.clear_table_button = QPushButton("Clear Table")
            self.clear_table_button.clicked.connect(self.clear_geo_table)
            
            self.export_table_button = QPushButton("Export Table")
            self.export_table_button.clicked.connect(self.export_geo_table)
            
            table_controls_layout.addWidget(self.clear_table_button)
            table_controls_layout.addWidget(self.export_table_button)
            table_controls_layout.addStretch(1)
            
            self.table_layout.addLayout(table_controls_layout)
            
            # Create the actual table for geological data
            self.geo_table = QTableWidget()
            self.geo_table.setColumnCount(6)
            self.geo_table.setHorizontalHeaderLabels(["기호 (Symbol)", "지층 (Stratum)", 
                                                    "대표암상 (Rock Type)", "시대 (Era)", 
                                                    "도폭 (Map Sheet)", "주소 (Address)"])
            self.geo_table.horizontalHeader().setStretchLastSection(True)
            self.geo_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            
            self.table_layout.addWidget(self.geo_table)
            
            self.splitter.addWidget(self.table_container)
            
            # Set initial splitter sizes (70% map, 30% table)
            self.splitter.setSizes([600, 200])
            
            # Create JavaScript handler for callbacks
            class JSHandler(QObject):
                popupInfoReceived = pyqtSignal(str)
            
            self.js_handler = JSHandler()
            self.js_handler.popupInfoReceived.connect(self.handle_popup_info)
            
            # Track login state
            self.login_attempted = False
            self.login_successful = False
            
            # Track info tool state
            self.info_tool_active = False
            
            # Current geological information
            self.current_geo_info = None
            
            # Current coordinates
            self.current_lat = None
            self.current_lng = None
            
            # Store the target map URL
            self.target_map_url = "https://data.kigam.re.kr/mgeo/map/main.do?process=geology_50k"
            
            # Load saved credentials if available
            self.load_saved_credentials()
            
            # Load the KIGAM website - updated to the correct login URL
            self.web_view.load(QUrl("https://data.kigam.re.kr/auth/login?redirect=/mgeo/sub01/page02.do"))
        
        def load_saved_credentials(self):
            """Load saved credentials from settings and apply them"""
            email = self.settings.value("email", "")
            password = self.settings.value("password", "")
            remember = self.settings.value("remember", False, type=bool)
            
            if email and password:
                self.email_input.setText(email)
                self.password_input.setText(password)
                self.remember_me.setChecked(remember)
                self.login_status.setText("Credentials loaded. Auto-login will begin when page loads.")
                
                # Update button states
                self.clear_credentials_button.setEnabled(True)
            else:
                self.clear_credentials_button.setEnabled(False)
                
        def save_credentials(self):
            """Save credentials to settings if remember me is checked"""
            if self.remember_me.isChecked():
                self.settings.setValue("email", self.email_input.text())
                self.settings.setValue("password", self.password_input.text())
                self.settings.setValue("remember", True)
                self.clear_credentials_button.setEnabled(True)
                debug_print("Credentials saved", 1)
            else:
                # If "remember me" is unchecked, clear any saved credentials
                self.clear_saved_credentials()
                
        def clear_saved_credentials(self):
            """Clear saved credentials from settings"""
            self.settings.remove("email")
            self.settings.remove("password")
            self.settings.remove("remember")
            self.login_status.setText("Saved credentials cleared")
            self.clear_credentials_button.setEnabled(False)
            debug_print("Credentials cleared", 1)
        
        def login_to_kigam(self):
            """Login to KIGAM website with the provided credentials"""
            email = self.email_input.text()
            password = self.password_input.text()
            
            if not email or not password:
                QMessageBox.warning(self, "Login Error", "Please enter both email and password")
                return
            
            # Save credentials if "remember me" is checked
            self.save_credentials()
            
            # Set login attempted flag
            self.login_attempted = True
            
            # Inject JavaScript to enter credentials and submit the form
            # Updated to match the KIGAM login form structure
            script = f"""
            (function() {{
                // Find the login form elements
                // Looking specifically for the KIGAM login form structure
                var emailInput = document.querySelector('input[placeholder="Email"]');
                var passwordInput = document.querySelector('input[type="password"]');
                var loginButton = document.querySelector('button[type="submit"], button.btn-primary, input[type="submit"]');
                
                if (emailInput && passwordInput) {{
                    // Update values
                    emailInput.value = "{email}";
                    passwordInput.value = "{password}";
                    
                    // Submit the form using the login button if found
                    if (loginButton) {{
                        loginButton.click();
                        return "Login initiated by clicking button";
                    }}
                    
                    // Fallback: Try to find and submit the form directly
                    var loginForm = emailInput.closest('form');
                    if (loginForm) {{
                        loginForm.submit();
                        return "Login form submitted";
                    }}
                    
                    return "Found login fields but couldn't submit form";
                }}
                
                return "Login form elements not found";
            }})();
            """
            
            self.web_view.page().runJavaScript(script, self.handle_login_result)
        
        def handle_login_result(self, result):
            """Handle the login JavaScript result"""
            debug_print(f"Login script result: {result}", 1)
            if "not found" in result:
                QMessageBox.warning(
                    self, 
                    "Login Form Not Found", 
                    "Could not locate the login form on the page. The website structure may have changed."
                )
        
        def on_page_load_finished(self, success):
            """Called when a page finishes loading"""
            if not success:
                self.statusBar().showMessage("Failed to load page", 3000)
                return
            
            current_url = self.web_view.url().toString()
            debug_print(f"Page loaded: {current_url}", 1)
            
            # Check for login form if we're on the login page
            if "auth/login" in current_url:
                # Check for saved credentials and auto-login if available
                if (self.email_input.text() and self.password_input.text() and 
                    self.settings.value("remember", False, type=bool)):
                    self.login_status.setText("Auto-logging in...")
                    QTimer.singleShot(500, self.login_to_kigam)  # Small delay to ensure page is fully loaded
                
                # Check if login form is ready and accessible
                self.web_view.page().runJavaScript(
                    """
                    (function() {
                        var emailField = document.querySelector('input[type="text"][placeholder="Email"]');
                        var passwordField = document.querySelector('input[type="password"][placeholder="Password"]');
                        var loginButton = document.querySelector('button.login-button');
                        
                        return {
                            emailField: !!emailField,
                            passwordField: !!passwordField,
                            loginButton: !!loginButton
                        };
                    })();
                    """,
                    self.handle_login_form_check
                )
            # If login was attempted and we're no longer on the login page,
            # assume login was successful
            elif self.login_attempted and "auth/login" not in current_url:
                self.login_successful = True
                self.login_status.setText("Login successful")
                
                # If we're now on some page in the KIGAM system but not yet 
                # at our target map, navigate there
                if "data.kigam.re.kr" in current_url and current_url != self.target_map_url:
                    debug_print(f"Login successful, navigating to geological map at: {self.target_map_url}", 1)
                    self.statusBar().showMessage("Login successful. Loading geological map...", 3000)
                    
                    # Navigate to the specific geological map URL
                    self.web_view.load(QUrl(self.target_map_url))
                    return
            
            # If we've reached the target map URL
            if current_url == self.target_map_url or "process=geology_50k" in current_url:
                debug_print("Successfully loaded geological map", 1)
                self.statusBar().showMessage("Geological map loaded successfully", 3000)
                self.login_status.setText("Logged in and map loaded successfully")
                
                # Set up monitoring for popups
                self.setup_map_interaction_monitoring()
        
        def handle_login_form_check(self, result):
            """Handle the check for login form readiness"""
            debug_print(f"Login form check result: {result}", 1)
            
            if isinstance(result, dict) and result.get("emailField") and result.get("passwordField"):
                self.statusBar().showMessage("Login form ready", 3000)
                if self.settings.value("remember", False, type=bool) and self.email_input.text() and self.password_input.text():
                    debug_print("Auto-login triggered", 1)
                    self.login_status.setText("Login form ready, auto-login processing...")
            else:
                self.statusBar().showMessage("Login form not ready or not found", 3000)
                self.login_status.setText("Unable to find login form. Please check the website structure.")
        
        def activate_info_tool(self, checked):
            """Activate the information tool on the map"""
            # Update the info tool state
            self.info_tool_active = checked
            
            if checked:
                debug_print(f"Info tool activated, checked state: {checked}", 0)  # Always show this message
                self.statusBar().showMessage("Info tool activated. Click on the map to see geological data.", 5000)
                
                # Update info label to show status
                self.info_label.setStyleSheet("background-color: rgba(255, 255, 200, 220); padding: 5px; border-radius: 3px;")
                self.info_label.setText("Activating info tool... please wait")
                
                # Set the flag in JavaScript to indicate the info tool is active
                self.web_view.page().runJavaScript(
                    """
                    window._infoToolActive = true;
                    console.log('Info tool flag set to active');
                    """,
                    lambda result: debug_print("Info tool flag set in JavaScript", 0)
                )
                
                # Specifically target the info button in the left menu based on the HTML structure you provided
                script = """
                (function() {
                    console.log('Searching for info button in left menu...');
                    
                    // Try to find the specific info button from your HTML
                    var infoButton = document.querySelector('a.btn_info, a.btn_info.active');
                    
                    if (!infoButton) {
                        console.log('Specific info button not found, trying more general selectors');
                        infoButton = document.querySelector('.left_btn a[href*="javascript:void(0)"] img[src*="info"]');
                    }
                    
                    if (!infoButton) {
                        console.log('Still not found, trying by image alt text');
                        var images = document.querySelectorAll('img');
                        for (var i = 0; i < images.length; i++) {
                            if (images[i].alt && images[i].alt.includes('정보')) {
                                infoButton = images[i].parentElement;
                                console.log('Found info button by image alt text');
                                break;
                            }
                        }
                    }
                    
                    if (!infoButton) {
                        // Try to find by image source
                        var images = document.querySelectorAll('img[src*="info"], img[src*="tool"]');
                        for (var i = 0; i < images.length; i++) {
                            console.log('Checking image:', images[i].src);
                            if (images[i].src.includes('info') || images[i].src.includes('tool')) {
                                infoButton = images[i].parentElement;
                                console.log('Found info button by image source:', images[i].src);
                                break;
                            }
                        }
                    }
                    
                    if (infoButton) {
                        console.log('Found info button:', infoButton.outerHTML.substring(0, 100));
                        // Save the element globally for debugging
                        window._infoButton = infoButton;
                        
                        // Click it!
                        infoButton.click();
                        
                        // Check if it has the "active" class after clicking
                        if (infoButton.classList.contains('active')) {
                            console.log('Info button has active class - this is good');
                        } else {
                            console.log('Info button does not have active class - attempting to add it');
                            infoButton.classList.add('active');
                        }
                        
                        // Also check if we need to call the function directly
                        if (infoButton.href && infoButton.href.includes('javascript:')) {
                            var funcMatch = infoButton.href.match(/javascript:(\\w+)\\(/);
                            if (funcMatch && funcMatch[1]) {
                                var funcName = funcMatch[1];
                                console.log('Trying to call function directly:', funcName);
                                if (window[funcName]) {
                                    window[funcName]();
                                }
                            }
                        }
                        
                        return "Info tool activated: " + infoButton.outerHTML.substring(0, 50);
                    }
                    
                    console.log('Last resort - searching for ANY link in the left menu');
                    var leftBtns = document.querySelector('.left_btn');
                    if (leftBtns) {
                        var links = leftBtns.querySelectorAll('a');
                        console.log('Found', links.length, 'links in left_btn');
                        // Click the 3rd link which is often the info button
                        if (links.length >= 3) {
                            links[2].click();
                            return "Clicked potential info button in left menu";
                        }
                    }
                    
                    // If we couldn't find a button, set up direct monitoring anyway
                    window._directInfoHandling = true;
                    return "Using direct info handling - no info button found";
                })();
                """
                
                debug_print("Injecting JavaScript to activate info button in left menu", 0)
                self.web_view.page().runJavaScript(script, self.handle_info_tool_activation)
            else:
                debug_print("Info tool deactivated", 0) # Always show this
                self.statusBar().showMessage("Info tool deactivated", 3000)
                self.info_label.setStyleSheet("background-color: rgba(255, 255, 255, 220); padding: 5px; border-radius: 3px;")
                self.info_label.setText("Info tool deactivated")
                
                # Set the flag in JavaScript to indicate the info tool is inactive
                self.web_view.page().runJavaScript(
                    """
                    window._infoToolActive = false;
                    window._directInfoHandling = false;
                    console.log('Info tool flag set to inactive');
                    
                    // If we saved the info button, try to deactivate it
                    if (window._infoButton) {
                        window._infoButton.classList.remove('active');
                        console.log('Removed active class from info button');
                    }
                    """,
                    lambda result: debug_print("Info tool flag set to inactive in JavaScript", 0)
                )
        
        def handle_info_tool_activation(self, result):
            """Handle the result of activating the info tool"""
            debug_print(f"Info tool activation result: {result}", 0)  # Always show this
            
            if "activated" in result.lower():
                self.statusBar().showMessage("Info tool activated. Click on the map to see geological data.", 5000)
                self.info_label.setStyleSheet("background-color: rgba(200, 255, 200, 220); padding: 5px; border-radius: 3px;")
                self.info_label.setText("Info tool activated - Click on the map to view geological information")
                
                # Check if we have monitoring set up
                self.web_view.page().runJavaScript(
                    """window._kigamMonitorSetup ? "Monitoring active" : "Monitoring not active";""",
                    lambda status: self.check_monitoring_status(status)
                )
            else:
                self.info_button.setChecked(False)
                self.info_tool_active = False
                self.statusBar().showMessage(f"Could not activate info tool: {result}", 5000)
                self.info_label.setStyleSheet("background-color: rgba(255, 200, 200, 220); padding: 5px; border-radius: 3px;")
                self.info_label.setText("Error: Could not find the info button on the map")
                
                QMessageBox.warning(
                    self,
                    "Info Tool Activation Failed",
                    f"Could not find the info button on the map. Result: {result}\n\n"
                    "Try these options:\n"
                    "1. Click the 'i' icon on the map manually\n"
                    "2. Make sure the map is fully loaded\n"
                    "3. Check if the map interface has an info button"
                )
        
        def check_monitoring_status(self, status):
            """Check if popup monitoring is active"""
            debug_print(f"Monitoring status: {status}", 0)
            if status != "Monitoring active":
                # Monitoring is not set up, try to set it up again
                debug_print("Popup monitoring not active, setting up again", 0)
                self.setup_map_interaction_monitoring()
        
        def setup_map_interaction_monitoring(self):
            """Set up monitoring for map interactions and popups"""
            debug_print("Setting up map interaction monitoring", 0)  # Always show this
            
            # First, inject the QWebChannel script to fix the "QWebChannel is not defined" error
            self.web_view.page().runJavaScript(
                """
                if (typeof QWebChannel === 'undefined') {
                    console.log('QWebChannel not found, will use direct method');
                    
                    // Create a simple polyfill for QWebChannel if the real one is not available
                    window.QWebChannel = function(transport, callback) {
                        console.log('Using QWebChannel polyfill');
                        window._channelCallback = callback;
                        window._registerObject = function(name, obj) {
                            var channel = { objects: {} };
                            channel.objects[name] = obj;
                            if (window._channelCallback) window._channelCallback(channel);
                        };
                    };
                }
                """,
                lambda result: debug_print("QWebChannel polyfill added if needed", 0)
            )
            
            # Add JavaScript callback handler for popup info - using a much simpler approach
            callback_script = """
                // Create a simple global handler for popup info
                window.sendPopupInfoToApp = function(content) {
                    console.log('Sending popup info to app:', content.substring(0, 50) + '...');
                    
                    // Store the content for retrieval
                    window._lastPopupContent = content;
                    
                    // Try different methods to send it back
                    if (window.qt && window.qt.popupInfoFound) {
                        console.log('Using qt.popupInfoFound');
                        window.qt.popupInfoFound(content);
                    } 
                    else if (window.jsCallback && window.jsCallback.popupInfoReceived) {
                        console.log('Using jsCallback.popupInfoReceived');
                        window.jsCallback.popupInfoReceived(content);
                    }
                    else {
                        console.log('Could not find a way to send info back to app');
                    }
                };
                
                window.qt = window.qt || {};
                window.qt.popupInfoFound = function(content) {
                    console.log('Popup info found:', content.substring(0, 50) + '...');
                    window._lastPopupContent = content;
                };
                
                // Add coordinate handler
                window.qt.coordinatesFound = function(coordInfo) {
                    console.log('Coordinates found:', JSON.stringify(coordInfo));
                    window._lastClickCoordinates = coordInfo;
                };
                
                // Debug function to dump OpenLayers information
                window.dumpOpenLayersInfo = function() {
                    var info = { objects: [] };
                    
                    // Look for map-related objects
                    for (var key in window) {
                        try {
                            if (key.startsWith('ol') || 
                                (window[key] && typeof window[key] === 'object' && 
                                 window[key].getView && typeof window[key].getView === 'function')) {
                                info.objects.push(key);
                            }
                        } catch (e) {}
                    }
                    
                    // Find map element
                    var mapElement = document.querySelector('.ol-viewport') || 
                                   document.querySelector('#map') || 
                                   document.querySelector('.map-container');
                    info.mapElementFound = !!mapElement;
                    
                    return JSON.stringify(info);
                };
            """
            
            debug_print("Setting up simplified JavaScript callback handler", 0)
            self.web_view.page().runJavaScript(callback_script, lambda result: debug_print("Callback script executed", 0))
            
            # Dump OpenLayers info for debugging
            debug_script = """
                if (window.dumpOpenLayersInfo) {
                    return window.dumpOpenLayersInfo();
                } else {
                    return "dumpOpenLayersInfo not available";
                }
            """
            self.web_view.page().runJavaScript(debug_script, lambda result: debug_print(f"OpenLayers info: {result}", 0))
            
            # Create a polling mechanism to retrieve popup content
            poll_script = """
                // Set up polling to retrieve popup content from JavaScript
                window._popupContentPollingInterval = setInterval(function() {
                    if (window._lastPopupContent) {
                        var content = window._lastPopupContent;
                        window._lastPopupContent = null; // Clear it so we don't keep retrieving it
                        
                        // Return the content - this will be passed to the lambda function
                        return content;
                    }
                    return null;
                }, 500);
            """
            
            debug_print("Setting up content polling", 0)
            # Run the polling script and set up a repeating timer to retrieve content
            self.web_view.page().runJavaScript(poll_script, lambda result: debug_print("Polling script executed", 0))
            
            # Set up a timer to poll for popup content
            self.popup_poll_timer = QTimer(self)
            self.popup_poll_timer.timeout.connect(self.poll_for_popup_content)
            self.popup_poll_timer.start(1000)  # Poll every 1 second
            
            # Set up channel to communicate with JavaScript
            debug_print("Setting up WebChannel for JavaScript communication", 0)
            channel = QWebChannel(self.web_view.page())
            channel.registerObject('jsCallback', self.js_handler)
            self.web_view.page().setWebChannel(channel)
            
            # Update web channel in JavaScript with fallback mechanism
            webchannel_script = """
                console.log('Setting up QWebChannel');
                try {
                    new QWebChannel(qt.webChannelTransport, function(channel) {
                        console.log('QWebChannel created, objects:', Object.keys(channel.objects).join(', '));
                        window.jsCallback = channel.objects.jsCallback;
                        console.log('jsCallback assigned:', window.jsCallback ? 'yes' : 'no');
                    });
                } catch (e) {
                    console.error('QWebChannel error:', e);
                }
            """
            
            self.web_view.page().runJavaScript(webchannel_script, 
                lambda result: debug_print("WebChannel script executed", 0))
            
            script = """
            (function() {
                // Check if we already set up the monitor
                if (window._kigamMonitorSetup) {
                    console.log('Monitor already set up, resetting');
                    // Clear any existing interval
                    if (window._popupCheckInterval) {
                        clearInterval(window._popupCheckInterval);
                        console.log('Cleared existing interval');
                    }
                }
                
                // Find map container - specifically looking for OpenLayers elements based on the HTML
                var mapContainer = document.querySelector('.ol-viewport, .ol-unselectable, canvas.ol-unselectable');
                if (!mapContainer) {
                    console.log('OpenLayers map container not found, trying generic selectors');
                    mapContainer = document.querySelector('#map1Map, #mapWrap, div[id*="map"], div[class*="map"]');
                    
                    if (!mapContainer) {
                        console.log('No map container found, falling back to document.body');
                        mapContainer = document.body; // Last resort
                    }
                }
                
                console.log('Using map container:', mapContainer.tagName, mapContainer.className);
                
                // Set flag to prevent multiple setups
                window._kigamMonitorSetup = true;
                
                // Set up click handler for the map to capture click events
                if (!window._mapClickHandlerSet) {
                    console.log('Setting up map click handler');
                    
                    // Add event listener to capture clicks on the map container
                    mapContainer.addEventListener('click', function(e) {
                        console.log('Map clicked at', e.clientX, e.clientY);
                        
                        if (window._infoToolActive) {
                            console.log('Info tool is active, will check for popups');
                            // Schedule popup check after a short delay to allow any popup to appear
                            setTimeout(function() {
                                checkForPopupInfo();
                            }, 500);
                        }
                    });
                    
                    window._mapClickHandlerSet = true;
                }
                
                // Actively search for the "popup layer" that might contain information
                function findElementsWithInfo() {
                    // Look for elements that might contain geological info
                    console.log('Actively searching for elements with info...');
                    
                    // 1. Try to find popup layers first
                    var popupLayers = document.querySelectorAll('.ol-popup, .popupLayer, .popup-layer, div[class*="popup"]');
                    
                    if (popupLayers.length > 0) {
                        console.log('Found popup layers:', popupLayers.length);
                        
                        // Check each popup layer for content
                        for (var i = 0; i < popupLayers.length; i++) {
                            var layer = popupLayers[i];
                            
                            // Check if it's visible
                            if (layer.offsetWidth > 0 && layer.offsetHeight > 0) {
                                console.log('Found visible popup layer:', layer.className);
                                var content = layer.innerText || layer.textContent;
                                
                                if (content && content.trim().length > 0) {
                                    console.log('Popup layer has content');
                                    window.sendPopupInfoToApp(content.trim());
                                    return true;
                                }
                            }
                        }
                    }
                    
                    // 2. Look for any visible tables that might have appeared
                    var tables = document.querySelectorAll('table');
                    for (var i = 0; i < tables.length; i++) {
                        var table = tables[i];
                        if (table.offsetWidth > 0 && table.offsetHeight > 0) {
                            var content = table.innerText || table.textContent;
                            if (content && content.trim().length > 5) {
                                console.log('Found visible table with content');
                                window.sendPopupInfoToApp(content.trim());
                                return true;
                            }
                        }
                    }
                    
                    // 3. Look for any new elements that appeared since last click
                    // This is a fallback for when popups don't use standard classes
                    if (window._lastElementSnapshot) {
                        var currentHTML = document.body.innerHTML;
                        if (currentHTML !== window._lastElementSnapshot) {
                            console.log('DOM has changed since last snapshot');
                            
                            // Find elements that are visible and contain text
                            var allElements = document.querySelectorAll('body *');
                            for (var i = 0; i < allElements.length; i++) {
                                var elem = allElements[i];
                                if (elem.offsetWidth > 0 && elem.offsetHeight > 0) {
                                    var text = elem.innerText || elem.textContent;
                                    // Only consider elements with substantial text
                                    if (text && text.trim().length > 20) {
                                        console.log('Found visible element with text:', elem.tagName);
                                        window.sendPopupInfoToApp(text.trim());
                                        return true;
                                    }
                                }
                            }
                        }
                    }
                    
                    // Update the snapshot for next time
                    window._lastElementSnapshot = document.body.innerHTML;
                    
                    return false;
                }
                
                // Function to check for and extract popup content
                function checkForPopupInfo() {
                    console.log('Checking for popup info...');
                    
                    // Try to use the site's built-in popup/info container/layer API
                    if (typeof getFeatureInfo === 'function') {
                        console.log('Found getFeatureInfo function, calling it');
                        try {
                            getFeatureInfo();
                            console.log('getFeatureInfo function called successfully');
                            // The function should trigger the popup display
                            setTimeout(function() {
                                findElementsWithInfo();
                            }, 500);
                            return;
                        } catch (e) {
                            console.error('Error calling getFeatureInfo:', e);
                        }
                    }
                    
                    // Use our own detection methods
                    return findElementsWithInfo();
                }
                
                // Set up interval to periodically check for popups (backup for click handler)
                console.log('Setting up popup check interval');
                window._popupCheckInterval = setInterval(function() {
                    if (window._infoToolActive) {
                        findElementsWithInfo();
                    }
                }, 2000);
                
                return "Map monitoring set up successfully for OpenLayers map";
            })();
            """
            
            # Run the script to set up monitoring
            self.web_view.page().runJavaScript(script, self.handle_monitor_setup_result)
            
            # Schedule a check after a short delay to verify everything is working
            QTimer.singleShot(2000, self.verify_monitoring)
            
            # Check if method exists before connecting timer
            has_poll_method = hasattr(self, 'poll_for_coordinates')
            debug_print(f"Has poll_for_coordinates method: {has_poll_method}", 0)
            
            if has_poll_method:
                # Start coordinate polling
                self.coordinate_timer = QTimer(self)
                self.coordinate_timer.timeout.connect(self.poll_for_coordinates)
                self.coordinate_timer.start(500)  # Poll every 500ms
            else:
                debug_print("WARNING: poll_for_coordinates method not found!", 0)
                # Define the method inline as a fallback
                def poll_for_coordinates_fallback(self):
                    """Fallback polling method for coordinates"""
                    debug_print("Using fallback coordinate polling method", 0)
                    self.web_view.page().runJavaScript(
                        "window._lastClickCoordinates ? JSON.stringify(window._lastClickCoordinates) : null;",
                        lambda result: debug_print(f"Coordinates (not processed): {result}", 0)
                    )
                
                # Dynamically add the method to the instance
                import types
                self.poll_for_coordinates = types.MethodType(poll_for_coordinates_fallback, self)
                
                # Now create and connect the timer
                self.coordinate_timer = QTimer(self)
                self.coordinate_timer.timeout.connect(self.poll_for_coordinates)
                self.coordinate_timer.start(500)  # Poll every 500ms
            
            # Add a direct coordinate capture script
            direct_capture = """
            (function() {
                console.log('Adding direct coordinate capture to KIGAM map');
                
                // Function to find OpenLayers map instance
                function findMap() {
                    // Check for global map variable
                    if (window.map && typeof window.map.getView === 'function') {
                        return window.map;
                    }
                    
                    // Look for map in global variables
                    for (var key in window) {
                        try {
                            if (typeof window[key] === 'object' && window[key] !== null) {
                                var obj = window[key];
                                if (typeof obj.getView === 'function' && 
                                    typeof obj.getTargetElement === 'function') {
                                    console.log('Found map in variable:', key);
                                    return obj;
                                }
                            }
                        } catch (e) {}
                    }
                    
                    // Look for map in DOM
                    var olElements = document.querySelectorAll('.ol-viewport');
                    for (var i = 0; i < olElements.length; i++) {
                        for (var prop in olElements[i]) {
                            if (prop.startsWith('__ol_')) {
                                try {
                                    var olProp = olElements[i][prop];
                                    if (olProp && olProp.map) {
                                        return olProp.map;
                                    }
                                } catch (e) {}
                            }
                        }
                    }
                    
                    return null;
                }
                
                var map = findMap();
                if (!map) {
                    console.error('Could not find map object for coordinate capture');
                    return "Map not found";
                }
                
                console.log('Found map for coordinate capture');
                
                // Add click handler to the map
                map.on('click', function(event) {
                    var coords = event.coordinate;
                    console.log('Map clicked at coordinates:', coords);
                    
                    var coordInfo = {
                        raw: coords,
                        timestamp: new Date().getTime()
                    };
                    
                    try {
                        // Add additional map information
                        coordInfo.projection = map.getView().getProjection().getCode();
                        coordInfo.zoom = map.getView().getZoom();
                        
                        // Convert to WGS84 coordinates
                        if (window.ol && window.ol.proj && typeof window.ol.proj.transform === 'function') {
                            var wgs84 = window.ol.proj.transform(
                                coords,
                                coordInfo.projection,
                                'EPSG:4326'
                            );
                            coordInfo.lng = wgs84[0];
                            coordInfo.lat = wgs84[1];
                            console.log('Converted to WGS84:', coordInfo.lat, coordInfo.lng);
                        }
                    } catch (e) {
                        console.error('Error processing coordinates:', e);
                    }
                    
                    // Store the coordinates for polling
                    window._lastClickCoordinates = coordInfo;
                    console.log('Stored coordinates:', JSON.stringify(coordInfo));
                });
                
                return "Direct coordinate capture added to map";
            })();
            """
            
            debug_print("Adding direct coordinate capture", 0)
            self.web_view.page().runJavaScript(direct_capture, lambda result: debug_print(f"Direct capture result: {result}", 0))
        
        def poll_for_popup_content(self):
            """Poll JavaScript for popup content"""
            if not self.info_tool_active:
                return
                
            self.web_view.page().runJavaScript(
                "window._lastPopupContent || null;",
                self.handle_polled_content
            )
        
        def handle_polled_content(self, content):
            """Handle content retrieved from polling"""
            if content:
                debug_print(f"Retrieved popup content from polling: {content[:50]}...", 0)
                self.handle_popup_info(content)
                
                # Clear the content in JavaScript
                self.web_view.page().runJavaScript(
                    "window._lastPopupContent = null;",
                    lambda result: None
                )
        
        def handle_monitor_setup_result(self, result):
            """Handle the result of setting up map monitoring"""
            debug_print(f"Map monitoring setup result: {result}", 0)  # Always show this
            if "successfully" in result:
                self.statusBar().showMessage("Map interaction monitoring active", 3000)
                self.info_label.setStyleSheet("background-color: rgba(200, 255, 200, 220); padding: 5px; border-radius: 3px;")
            else:
                self.statusBar().showMessage(f"Map monitoring issue: {result}", 5000)
                self.info_label.setStyleSheet("background-color: rgba(255, 240, 200, 220); padding: 5px; border-radius: 3px;")
                self.info_label.setText(f"Warning: Map monitoring setup issue: {result}")
        
        def verify_monitoring(self):
            """Verify that monitoring is set up and working"""
            debug_print("Verifying popup monitoring setup", 0)
            check_script = """
            (function() {
                var status = {
                    monitorSetup: !!window._kigamMonitorSetup,
                    intervalActive: !!window._popupCheckInterval,
                    qtHandler: !!window.qt,
                    popupHandler: window.qt ? !!window.qt.popupInfoFound : false,
                    jsCallback: !!window.jsCallback
                };
                return JSON.stringify(status);
            })();
            """
            
            self.web_view.page().runJavaScript(check_script, lambda result: self.handle_verify_result(result))
            
        def handle_verify_result(self, result):
            """Handle the monitoring verification result"""
            try:
                status = json.loads(result)
                debug_print("Monitoring status:", 0)
                debug_print(f"  Monitor setup: {status['monitorSetup']}", 0)
                debug_print(f"  Interval active: {status['intervalActive']}", 0)
                debug_print(f"  Qt handler available: {status['qtHandler']}", 0)
                debug_print(f"  Popup handler available: {status['popupHandler']}", 0)
                debug_print(f"  JS callback available: {status['jsCallback']}", 0)
                
                if not all([status['monitorSetup'], status['intervalActive'], 
                           status['qtHandler'], status['popupHandler']]):
                    debug_print("Monitoring not fully set up, attempting to fix", 0)
                    self.setup_map_interaction_monitoring()
                    
                # Update the info label with monitoring status
                if all([status['monitorSetup'], status['intervalActive'], 
                       status['qtHandler'], status['popupHandler'], status['jsCallback']]):
                    self.info_label.setText("Info tool active and monitoring ready - Click on the map to view information")
                    self.info_label.setStyleSheet("background-color: rgba(200, 255, 200, 220); padding: 5px; border-radius: 3px;")
                else:
                    problems = []
                    if not status['monitorSetup']: problems.append("Monitor not set up")
                    if not status['intervalActive']: problems.append("Check interval not active")
                    if not status['popupHandler']: problems.append("Popup handler missing")
                    if not status['jsCallback']: problems.append("JS callback missing")
                    
                    self.info_label.setText(f"Warning: Monitoring has issues: {', '.join(problems)}")
                    self.info_label.setStyleSheet("background-color: rgba(255, 240, 200, 220); padding: 5px; border-radius: 3px;")
                
            except json.JSONDecodeError:
                debug_print(f"Could not parse verification result: {result}", 0)
                
        def handle_popup_info(self, content):
            """Handle the geological information from a map popup"""
            debug_print(f"Popup information received: {content}", 0)  # Always show this
            
            if content:
                # Store the current content for adding to table
                self.current_geo_info = content
                
                # Parse the information
                info_dict = self.parse_geological_info(content)
                
                if info_dict:
                    # Format a compact display string
                    compact_info = f"Symbol: {info_dict.get('symbol', 'N/A')} | Stratum: {info_dict.get('stratum', 'N/A')} | Rock: {info_dict.get('rock_type', 'N/A')} | Era: {info_dict.get('era', 'N/A')}"
                    
                    # Display in the QLineEdit
                    self.info_label.setText(compact_info)
                    self.info_label.setStyleSheet("background-color: rgba(220, 255, 220, 240); padding: 2px; border-radius: 3px; border: 1px solid green;")
                else:
                    self.info_label.setText("Could not parse geological information")
                    self.info_label.setStyleSheet("background-color: rgba(255, 240, 200, 220); padding: 2px; border-radius: 3px;")
                
                # Enable the add to table button
                self.add_to_table_button.setEnabled(True)
                
                # Flash the label briefly to indicate new data
                current_style = self.info_label.styleSheet()
                self.info_label.setStyleSheet("background-color: rgba(100, 255, 100, 240); padding: 2px; border-radius: 3px; border: 2px solid green;")
                QTimer.singleShot(300, lambda: self.info_label.setStyleSheet(current_style))
                
                # Log the content for debugging
                debug_print(f"Content received: {content}", 0)
            else:
                self.current_geo_info = None
                self.add_to_table_button.setEnabled(False)
                self.info_label.setText("No geological information found")
                self.info_label.setStyleSheet("background-color: rgba(255, 240, 200, 220); padding: 2px; border-radius: 3px;")
                self.statusBar().showMessage("No information found at clicked location", 3000)

        def update_coordinates(self, lat, lng):
            """Update the coordinate display with WGS84 coordinates"""
            debug_print(f"Updating coordinates display: {lat}, {lng}", 0)
            self.current_lat = lat
            self.current_lng = lng
            
            # Format the coordinate display
            self.coords_label.setText(f"Coordinates: Lat {lat:.6f}, Lng {lng:.6f}")
            
            # Check if we have geological information to add to the table
            if self.current_geo_info:
                self.add_to_table_button.setEnabled(True)
            
            self.statusBar().showMessage(f"Coordinates updated: Lat {lat:.6f}, Lng {lng:.6f}", 2000)
        
        def add_current_info_to_table(self):
            """Add current geological information to the table"""
            if not self.current_geo_info:
                QMessageBox.warning(self, "No Data", "No geological information available to add")
                return
            
            # Parse the information to extract fields
            info_dict = self.parse_geological_info(self.current_geo_info)
            
            if info_dict:
                # Add a new row to the table
                row_position = self.geo_table.rowCount()
                self.geo_table.insertRow(row_position)
                
                # Add the extracted information to the cells
                self.geo_table.setItem(row_position, 0, QTableWidgetItem(info_dict.get('symbol', '')))
                self.geo_table.setItem(row_position, 1, QTableWidgetItem(info_dict.get('stratum', '')))
                self.geo_table.setItem(row_position, 2, QTableWidgetItem(info_dict.get('rock_type', '')))
                self.geo_table.setItem(row_position, 3, QTableWidgetItem(info_dict.get('era', '')))
                self.geo_table.setItem(row_position, 4, QTableWidgetItem(info_dict.get('map_sheet', '')))
                self.geo_table.setItem(row_position, 5, QTableWidgetItem(info_dict.get('address', '')))
                
                # Determine how many columns are needed for coordinates
                needed_columns = 6  # Basic info columns
                
                # Check if we have raw map coordinates or WGS84 coordinates
                has_raw_coords = hasattr(self, 'current_raw_x') and hasattr(self, 'current_raw_y')
                has_wgs84_coords = hasattr(self, 'current_lat') and hasattr(self, 'current_lng')
                
                if has_raw_coords or has_wgs84_coords:
                    if has_raw_coords and has_wgs84_coords:
                        needed_columns = 10  # Both coordinate types (6 basic + 2 raw + 2 WGS84)
                    else:
                        needed_columns = 8  # Only one coordinate type (6 basic + 2 coords)
                    
                    # Expand the table if needed
                    if self.geo_table.columnCount() < needed_columns:
                        self.geo_table.setColumnCount(needed_columns)
                        headers = []
                        for i in range(6):
                            headers.append(self.geo_table.horizontalHeaderItem(i).text())
                        
                        if has_raw_coords and has_wgs84_coords:
                            # Add headers for both coordinate types
                            headers.extend(["X 좌표", "Y 좌표", "위도 (Latitude)", "경도 (Longitude)"])
                        elif has_raw_coords:
                            # Add headers for raw coordinates only
                            headers.extend(["X 좌표", "Y 좌표"])
                        else:
                            # Add headers for WGS84 coordinates only
                            headers.extend(["위도 (Latitude)", "경도 (Longitude)"])
                            
                        self.geo_table.setHorizontalHeaderLabels(headers)
                
                # Add raw map coordinates if available
                if has_raw_coords:
                    col_offset = 6  # Start after the basic info columns
                    self.geo_table.setItem(row_position, col_offset, QTableWidgetItem(str(self.current_raw_x)))
                    self.geo_table.setItem(row_position, col_offset + 1, QTableWidgetItem(str(self.current_raw_y)))
                    
                    # Add projection info to a tooltip
                    if hasattr(self, 'current_projection'):
                        projection_info = f"Projection: {self.current_projection}"
                        x_item = self.geo_table.item(row_position, col_offset)
                        y_item = self.geo_table.item(row_position, col_offset + 1)
                        if x_item and y_item:
                            x_item.setToolTip(projection_info)
                            y_item.setToolTip(projection_info)
                
                # Add WGS84 coordinates if available
                if has_wgs84_coords:
                    # Determine where to place the WGS84 coordinates
                    if has_raw_coords:
                        col_offset = 8  # After raw coordinates
                    else:
                        col_offset = 6  # After basic info columns
                    
                    self.geo_table.setItem(row_position, col_offset, QTableWidgetItem(str(self.current_lat)))
                    self.geo_table.setItem(row_position, col_offset + 1, QTableWidgetItem(str(self.current_lng)))
                
                # Select the new row
                self.geo_table.selectRow(row_position)
                
                # Show confirmation
                self.statusBar().showMessage(f"Added geological information to row {row_position + 1}", 3000)
            else:
                QMessageBox.warning(self, "Parsing Error", "Could not parse the geological information")
        
        def parse_geological_info(self, content):
            """Parse the geological information text to extract structured data"""
            # Initialize the dictionary to store the extracted information
            info_dict = {
                'symbol': '',
                'stratum': '',
                'rock_type': '',
                'era': '',
                'map_sheet': '',
                'address': ''
            }
            
            # Split the content into lines
            lines = content.strip().split('\n')
            
            # Extract information using pattern matching
            for line in lines:
                line = line.strip()
                
                # Symbol (기호)
                if '기호' in line or 'symbol' in line.lower():
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        info_dict['symbol'] = parts[1].strip()
                
                # Stratum (지층)
                elif '지층' in line or 'stratum' in line.lower():
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        info_dict['stratum'] = parts[1].strip()
                
                # Rock Type (대표암상)
                elif '대표암상' in line or 'rock' in line.lower():
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        info_dict['rock_type'] = parts[1].strip()
                
                # Era (시대)
                elif '시대' in line or 'era' in line.lower():
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        info_dict['era'] = parts[1].strip()
                
                # Map Sheet (도폭)
                elif '도폭' in line or 'map sheet' in line.lower():
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        info_dict['map_sheet'] = parts[1].strip()
                
                # Address (주소)
                elif '주소' in line or 'address' in line.lower():
                    # Special handling for address which might be on a separate line
                    parts = line.split(':', 1)
                    if len(parts) > 1 and parts[1].strip():
                        info_dict['address'] = parts[1].strip()
                    elif len(lines) > lines.index(line) + 1 and not ':' in lines[lines.index(line) + 1]:
                        # If the next line doesn't have a colon, it might be the address
                        next_line = lines[lines.index(line) + 1].strip()
                        if next_line and not next_line.startswith('인쇄') and not next_line.startswith('오류'):
                            info_dict['address'] = next_line
            
            # If minimal extraction was successful
            if info_dict['symbol'] or info_dict['stratum']:
                return info_dict
            else:
                # Try a fallback method - look for Korean characters followed by ":"
                korean_regex = re.compile(r'([가-힣]+)\s*:\s*([^\n]+)')
                matches = korean_regex.findall(content)
                
                for match in matches:
                    key, value = match
                    if '기호' in key:
                        info_dict['symbol'] = value.strip()
                    elif '지층' in key:
                        info_dict['stratum'] = value.strip()
                    elif '대표암상' in key:
                        info_dict['rock_type'] = value.strip()
                    elif '시대' in key:
                        info_dict['era'] = value.strip()
                    elif '도폭' in key:
                        info_dict['map_sheet'] = value.strip()
                    elif '주소' in key:
                        info_dict['address'] = value.strip()
                
                return info_dict
        
        def clear_geo_table(self):
            """Clear all rows from the geological data table"""
            if self.geo_table.rowCount() > 0:
                reply = QMessageBox.question(
                    self, 'Confirm Clear', 
                    'Are you sure you want to clear all geological data?',
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    self.geo_table.setRowCount(0)
                    self.statusBar().showMessage("Table cleared", 3000)
            else:
                self.statusBar().showMessage("Table is already empty", 3000)
        
        def export_geo_table(self):
            """Export the geological data table to a CSV file"""
            if self.geo_table.rowCount() == 0:
                QMessageBox.warning(self, "Export Error", "No data to export")
                return
            
            # Open file dialog to select save location
            file_name, _ = QFileDialog.getSaveFileName(
                self, "Export Geological Data", "", "CSV Files (*.csv);;All Files (*)"
            )
            
            if not file_name:
                return  # User canceled
                
            try:
                with open(file_name, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    
                    # Write headers
                    headers = []
                    for column in range(self.geo_table.columnCount()):
                        headers.append(self.geo_table.horizontalHeaderItem(column).text())
                    writer.writerow(headers)
                    
                    # Write data rows
                    for row in range(self.geo_table.rowCount()):
                        row_data = []
                        for column in range(self.geo_table.columnCount()):
                            item = self.geo_table.item(row, column)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)
                
                self.statusBar().showMessage(f"Data exported to {file_name}", 3000)
                
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Error exporting data: {str(e)}")
        
        def poll_for_coordinates(self):
            """Poll JavaScript for coordinates from map clicks"""
            self.web_view.page().runJavaScript(
                """
                (function() {
                    if (window._lastClickCoordinates) {
                        var coordInfo = window._lastClickCoordinates;
                        window._lastClickCoordinates = null; // Clear after reading
                        
                        try {
                            // Make sure we can stringify the object
                            var json = JSON.stringify(coordInfo);
                            return json;
                        } catch (e) {
                            console.error('Error stringifying coordinates:', e);
                            
                            // Try to extract at least some data if stringification fails
                            var basicInfo = {
                                error: 'Could not stringify full coordinates'
                            };
                            
                            // Try to extract lat/lng
                            if (coordInfo.lat !== undefined && coordInfo.lng !== undefined) {
                                basicInfo.lat = coordInfo.lat;
                                basicInfo.lng = coordInfo.lng;
                            }
                            
                            // Try to extract raw coordinates
                            if (Array.isArray(coordInfo.raw)) {
                                basicInfo.raw = coordInfo.raw;
                            }
                            
                            return JSON.stringify(basicInfo);
                        }
                    }
                    return null;
                })();
                """,
                self.handle_coordinate_polling
            )
        
        def handle_coordinate_polling(self, result):
            """Process coordinates retrieved from polling"""
            if not result:
                return
                
            try:
                coord_info = json.loads(result)
                debug_print(f"Received coordinate data: {coord_info}", 1)
                
                # Store raw coordinates and additional information
                self.last_coord_info = coord_info
                
                # Extract raw map coordinates if available
                raw_coords = coord_info.get('raw')
                
                if raw_coords and isinstance(raw_coords, list) and len(raw_coords) >= 2:
                    # Use raw coordinates in native map projection
                    x_coord = raw_coords[0] 
                    y_coord = raw_coords[1]
                    projection = coord_info.get('projection', 'Unknown')
                    
                    debug_print(f"Raw map coordinates: X={x_coord}, Y={y_coord} ({projection})", 0)
                    self.update_raw_coordinates(x_coord, y_coord, projection, coord_info)
                    
                # If lat/lng is available (converted to WGS84), also update those
                lat = coord_info.get('lat')
                lng = coord_info.get('lng')
                
                if lat is not None and lng is not None:
                    self.update_coordinates(lat, lng)
                
                # Clear the coordinates in JavaScript
                self.web_view.page().runJavaScript(
                    "window._lastClickCoordinates = null;",
                    lambda result: None
                )
            except json.JSONDecodeError as e:
                debug_print(f"Error decoding coordinates: {e}", 0)
        
        def update_raw_coordinates(self, x, y, projection, coord_info=None):
            """Update and store the raw map coordinates in their native format"""
            debug_print(f"Raw coordinates: {x}, {y} in projection {projection}", 0)
            
            # Store the raw coordinates
            self.current_raw_x = x
            self.current_raw_y = y
            self.current_projection = projection
            
            # Update coordinate display with raw coordinates
            self.coords_label.setText(f"Coordinates: X {x:.2f}, Y {y:.2f} ({projection})")
            
            # If we have lat/lng from coord_info, update those too
            if coord_info and 'lat' in coord_info and 'lng' in coord_info:
                lat = coord_info['lat']
                lng = coord_info['lng']
                self.current_lat = lat
                self.current_lng = lng
                
                # Update the display to show both raw and WGS84 coordinates
                self.coords_label.setText(
                    f"Map: X {x:.2f}, Y {y:.2f} | WGS84: Lat {lat:.6f}, Lng {lng:.6f}"
                )
            
            # Indicate if we have geological info that can be added to the table
            if self.current_geo_info:
                self.add_to_table_button.setEnabled(True)
                
            self.statusBar().showMessage(f"Coordinates updated", 2000)
        
        def update_coordinates(self, lat, lng):
            """Update the displayed WGS84 coordinates and store them"""
            debug_print(f"WGS84 coordinates: Lat={lat}, Lng={lng}", 0)
            
            # Round to 6 decimal places (approx. 10cm precision)
            lat_formatted = round(float(lat), 6)
            lng_formatted = round(float(lng), 6)
            
            # Store the coordinates
            self.current_lat = lat_formatted
            self.current_lng = lng_formatted
            
            # If we're already showing raw coordinates, don't overwrite the display
            if not hasattr(self, 'current_raw_x'):
                # Update the label with formatted coordinates
                self.coord_label.setText(f"WGS84: {lat_formatted}, {lng_formatted}")
                self.coord_label.setStyleSheet("background-color: rgba(200, 230, 255, 240); padding: 5px; border-radius: 3px; border: 1px solid blue;")
                
                # Flash the label to indicate new data
                current_style = self.coord_label.styleSheet()
                self.coord_label.setStyleSheet("background-color: rgba(120, 180, 255, 240); padding: 5px; border-radius: 3px; border: 2px solid blue;")
                QTimer.singleShot(300, lambda: self.coord_label.setStyleSheet(current_style))
                
                self.statusBar().showMessage(f"Map clicked at: {lat_formatted}, {lng_formatted}", 3000)


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
        
        # Add KIGAM map button
        self.kigam_map_button = QPushButton("KIGAM Map")
        self.kigam_map_button.setToolTip("Open KIGAM geological map in new window")
        self.kigam_map_button.clicked.connect(self.open_kigam_map)
        button_layout.addWidget(self.kigam_map_button)
        
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
        
        # Create filter button container with flow layout
        self.filter_widget = QWidget()
        self.filter_layout = FlowLayout(self.filter_widget, margin=2, spacing=2)
        self.filter_layout.setContentsMargins(2, 2, 2, 2)
        self.filter_widget.setLayout(self.filter_layout)
        
        # Change from Fixed to Minimum for vertical policy to allow necessary growth
        self.filter_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        # Add the filter widget directly to the main layout
        main_layout.addWidget(self.filter_widget)
        # Keep this to prevent unnecessary stretching
        main_layout.setStretchFactor(self.filter_widget, 0)
        
        # Use a splitter for resizable panels
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Create image viewer
        self.image_viewer = ImageViewer()
        
        # Create table view with proxy model for filtering
        self.table_view = QTableView()
        self.table_model = DikeTableModel()
        
        # Create custom proxy model for filtering and sequential numbering
        self.proxy_model = SequentialNumberProxyModel()
        self.proxy_model.setSourceModel(self.table_model)
        self.proxy_model.setFilterKeyColumn(12)  # Filter on "사진 이름" column
        self.proxy_model.setSortRole(Qt.UserRole)  # Use UserRole for sorting
        self.table_view.setModel(self.proxy_model)
        
        # Adjust table properties
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(True)
        
        # Connect table selection to image loading
        self.table_view.selectionModel().selectionChanged.connect(self.on_row_selected)
        
        # Set initial sort order - sequence column (0) in ascending order
        self.table_view.sortByColumn(0, Qt.AscendingOrder)
        
        # Add widgets to splitter
        self.splitter.addWidget(self.image_viewer)
        self.splitter.addWidget(self.table_view)
        
        # Set initial sizes
        self.splitter.setSizes([600, 600])
        
        # Add splitter to main layout
        main_layout.addWidget(self.splitter, 1)  # Give it a stretch factor of 1
        
        # Adjust the stretch factors to prioritize the splitter
        main_layout.setStretchFactor(self.splitter, 10)  # Give the splitter much more stretch priority

        # Set default image directory to './data'
        self.set_default_image_directory()
        
        # Try to find and load Excel file from data directory
        self.load_excel_from_data_dir()
        
        # Store the current filter
        self.current_filter = ""

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
            
            # Update image filter buttons
            self.update_image_filter_buttons()
    
    def update_image_filter_buttons(self):
        """Create buttons for each available image file in the directory"""
        # Clear existing buttons
        for i in reversed(range(self.filter_layout.count())): 
            item = self.filter_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # If no directory is set, just return
        if not self.image_viewer.image_dir or not os.path.exists(self.image_viewer.image_dir):
            debug_print("No valid image directory to create filter buttons", 1)
            return
        
        # Add "All" button first
        all_button = QPushButton("All")
        all_button.setToolTip("Show all records")
        all_button.setCheckable(True)
        all_button.setChecked(True)  # Default to checked
        all_button.clicked.connect(lambda: self.filter_table(""))
        all_button.setStyleSheet("background-color: #e6f2ff; font-weight: bold;")
        # Make buttons a bit taller to show text fully
        all_button.setFixedHeight(24)
        all_button.setMinimumWidth(40)
        all_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.filter_layout.addWidget(all_button)
        
        # Find all image files in the directory
        image_files = []
        unique_prefixes = set()
        prefix_to_image = {}  # Maps prefix to image file path
        
        for filename in os.listdir(self.image_viewer.image_dir):
            file_path = os.path.join(self.image_viewer.image_dir, filename)
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                image_files.append(file_path)
                
                # Extract prefix (e.g., "0. 마전리" from filename)
                for row in range(self.table_model.rowCount()):
                    photo_name = self.table_model.get_photo_name(row)
                    if photo_name and photo_name in filename:
                        unique_prefixes.add(photo_name)
                        # Store the first matching image file for this prefix
                        if photo_name not in prefix_to_image:
                            prefix_to_image[photo_name] = file_path
                        break
        
        # Sort the prefixes for consistent ordering
        sorted_prefixes = sorted(list(unique_prefixes))
        
        debug_print(f"Found {len(sorted_prefixes)} unique image prefixes", 1)
        
        # Create a button for each unique prefix
        for prefix in sorted_prefixes:
            if not prefix.strip():
                continue
            
            button = QPushButton(prefix)
            button.setToolTip(f"Show only records for {prefix}")
            button.setCheckable(True)
            
            # Store the image path in the button's data
            if prefix in prefix_to_image:
                image_path = prefix_to_image[prefix]
                # Create a closure that captures both prefix and image_path
                button.clicked.connect(lambda checked, p=prefix, img=image_path: self.filter_and_load_image(p, img))
            else:
                # Fallback if no image found
                button.clicked.connect(lambda checked, p=prefix: self.filter_table(p))
            
            # Make buttons a bit taller to show text fully
            button.setFixedHeight(24)
            button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            self.filter_layout.addWidget(button)

    def filter_and_load_image(self, prefix, image_path):
        """Filter the table by prefix and load the image with markers for all matching rows"""
        # First filter the table
        self.filter_table(prefix)
        
        # Then load the image
        debug_print(f"Loading image: {image_path}", 1)
        success = self.image_viewer.set_image(image_path)
        
        if success:
            debug_print(f"Successfully loaded image for prefix: {prefix}", 1)
            
            # Collect coordinates for all visible rows that match this prefix
            coordinates = []
            sequence_numbers = []
            
            for proxy_row in range(self.proxy_model.rowCount()):
                try:
                    # Get source model row index
                    source_row = self.proxy_model.mapToSource(
                        self.proxy_model.index(proxy_row, 0)).row()
                    
                    # Get X and Y coordinates (still at indices 9 and 10 in data array)
                    x_coord = float(self.table_model.data[source_row][9])  # 좌표 X
                    y_coord = float(self.table_model.data[source_row][10])  # 좌표 Y
                    coordinates.append((x_coord, y_coord))
                    # Use the display sequence number (proxy_row + 1)
                    sequence_numbers.append(proxy_row + 1)
                except (ValueError, IndexError) as e:
                    debug_print(f"Error getting coordinates for row {proxy_row}: {e}", 0)
            
            # Set all markers with primary indicated
            if coordinates:
                self.image_viewer.set_multiple_markers(coordinates, None, sequence_numbers)
                debug_print(f"Added {len(coordinates)} markers to the image", 1)
            
            # Fit the image to the window
            self.image_viewer.image_display.fit_to_window()
            
            # Update status message
            self.statusBar().showMessage(f"Loaded image for {prefix} with {len(coordinates)} markers", 3000)
        else:
            debug_print(f"Failed to load image for prefix: {prefix}", 0)

    def try_set_marker_from_table(self, prefix):
        """Try to find coordinates in the filtered table and set a marker"""
        # Look through the visible (filtered) rows for the first row with this prefix
        for row in range(self.proxy_model.rowCount()):
            proxy_idx = self.proxy_model.index(row, 11)  # 11 is the column for "사진 이름"
            photo_name = self.proxy_model.data(proxy_idx)
            
            if photo_name == prefix:
                # Found a matching row, map to source model
                source_row = self.proxy_model.mapToSource(proxy_idx).row()
                
                try:
                    # Get coordinates
                    x_coord = float(self.table_model.data[source_row][9])  # 좌표 X
                    y_coord = float(self.table_model.data[source_row][10])  # 좌표 Y
                    debug_print(f"Found coordinates for {prefix}: X={x_coord}, Y={y_coord}", 1)
                    
                    # Set marker
                    self.image_viewer.set_marker(x_coord, y_coord)
                    
                    # Check if we should center on the marker
                    if self.center_checkbox.isChecked():
                        # Center on marker with 200% zoom
                        self.image_viewer.image_display.set_zoom_level(2.0)
                        self.image_viewer.image_display.center_on_marker()
                    else:
                        # Fit to window
                        self.image_viewer.image_display.fit_to_window()
                
                    # Found one, no need to continue
                    break
                    
                except (ValueError, IndexError) as e:
                    debug_print(f"Error getting coordinates: {e}", 0)

    def filter_table(self, prefix):
        """Filter the table to show only rows with the given prefix"""
        debug_print(f"Filtering table to show: {prefix or 'All'}", 1)
        
        # Update all buttons to unchecked except the clicked one
        for i in range(self.filter_layout.count()):
            item = self.filter_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QPushButton):
                widget = item.widget()
                if (widget.text() == "All" and prefix == "") or (widget.text() == prefix):
                    widget.setChecked(True)
                    widget.setStyleSheet("background-color: #e6f2ff; font-weight: bold;")
                else:
                    widget.setChecked(False)
                    widget.setStyleSheet("")
        
        # Store current filter
        self.current_filter = prefix
        
        # Apply filter to the proxy model - note that column 11 in data becomes column 12 in display
        self.proxy_model.setFilterKeyColumn(12)  # Filter on "사진 이름" column
        self.proxy_model.setFilterFixedString(prefix)
        
        # Update status bar with count
        filtered_count = self.proxy_model.rowCount()
        total_count = self.table_model.rowCount()
        
        if prefix:
            self.statusBar().showMessage(f"Showing {filtered_count} of {total_count} records for {prefix}", 5000)
        else:
            self.statusBar().showMessage(f"Showing all {total_count} records", 5000)
    
    def on_row_selected(self, selected, deselected):
        """Handle row selection in the table view"""
        indexes = selected.indexes()
        if indexes:
            # Get the selected row - use the proxy model index
            proxy_row = indexes[0].row()
            # Map to the source model
            source_row = self.proxy_model.mapToSource(indexes[0]).row()
            debug_print(f"Row {proxy_row} selected (source row: {source_row})", 1)
            
            # Get the photo name from the selected row
            photo_name = self.table_model.get_photo_name(source_row)
            debug_print(f"Photo name: {photo_name}", 1)
            
            # Try to find and display the corresponding image
            if photo_name:
                success = self.image_viewer.set_image_by_name(photo_name)
                if success:
                    # Collect coordinates for all rows with this photo name
                    coordinates = []
                    sequence_numbers = []
                    primary_index = None
                    
                    # Loop through all rows in the source model to find matching photo names
                    for row in range(self.table_model.rowCount()):
                        row_photo_name = self.table_model.get_photo_name(row)
                        if row_photo_name == photo_name:
                            try:
                                # Note: The actual columns in the data are now at index-1 due to sequence column
                                x_coord = float(self.table_model.data[row][9])  # 좌표 X (still at index 9 in data array)
                                y_coord = float(self.table_model.data[row][10])  # 좌표 Y (still at index 10 in data array)
                                coordinates.append((x_coord, y_coord))
                                
                                # Find the display sequence number for this row
                                for proxy_row in range(self.proxy_model.rowCount()):
                                    if self.proxy_model.mapToSource(self.proxy_model.index(proxy_row, 0)).row() == row:
                                        # Add the sequence number (proxy_row + 1)
                                        sequence_numbers.append(proxy_row + 1)
                                        break
                                else:
                                    # If row not found in proxy model (filtered out), use source row + 1
                                    sequence_numbers.append(row + 1)
                                
                                # If this is the selected row, mark its index
                                if row == source_row:
                                    primary_index = len(coordinates) - 1
                                
                            except (ValueError, IndexError) as e:
                                debug_print(f"Error getting coordinates for row {row}: {e}", 0)
                    
                    # Set all markers with primary indicated
                    if coordinates:
                        self.image_viewer.set_multiple_markers(coordinates, primary_index, sequence_numbers)
                        debug_print(f"Added {len(coordinates)} markers to the image (primary: {primary_index})", 1)
                        
                        # Check if we should center on the selected marker
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
            
            # Update image filter buttons after loading data
            self.update_image_filter_buttons()
        
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
                
                # Update image filter buttons after loading data
                self.update_image_filter_buttons()
            else:
                QMessageBox.warning(
                    self, 
                    "Error Loading Excel",
                    f"Failed to load data from the selected Excel file."
                )

    def open_kigam_map(self):
        """Open the KIGAM geological map in a new window"""
        if WEB_ENGINE_AVAILABLE:
            self.kigam_window = KIGAMMapWindow()
            self.kigam_window.show()
        else:
            QMessageBox.warning(
                self, 
                "KIGAM Map Feature Disabled",
                "PyQt5.QtWebEngineWidgets not found. KIGAM map feature will be disabled."
            )


# We need to customize the proxy model to reset sequence numbers in filtered view
class SequentialNumberProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._sort_ascending = True  # Track sort direction
    
    def data(self, index, role=Qt.DisplayRole):
        # For the sequence number column, we'll return the visible row position + 1
        if index.column() == 0:
            if role == Qt.DisplayRole:
                # Return the visual position of this row + 1
                return str(index.row() + 1)
            elif role == Qt.UserRole:  # For sorting
                # Return a value that will sort properly in the expected direction
                row_num = index.row() + 1
                return row_num
        
        # For all other columns, use the source model data
        return super().data(index, role)

    def sort(self, column, order):
        # Call the parent class's sort method
        super().sort(column, order)
        
        # If we sorted by sequence number, we need to invalidate our display
        # since the row numbers need to be recalculated
        if column == 0:
            self.beginResetModel()
            self.endResetModel()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DikeFinderApp()
    window.show()
    sys.exit(app.exec_()) 


''' 
How to make an exe file

pyinstaller --name "DikeFinder_v0.0.2.exe" --onefile --noconsole main.py
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