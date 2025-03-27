import sys
import os
import datetime
import json
import csv
import re
import math
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import pandas as pd
import numpy as np
from pyproj import Transformer
from geopy.distance import geodesic
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                            QTableWidget, QTableWidgetItem, QMessageBox, 
                            QFileDialog, QCheckBox, QHeaderView, QSizePolicy,
                            QLayout, QSplitter, QToolBar, QDialog)
from PyQt5.QtCore import Qt, QUrl, QObject, pyqtSignal, QTimer, QSettings
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtGui import QIcon, QFont
from DikeModels import DikeRecord, init_database, db, DB_PATH
import shutil

# Company and program information
COMPANY_NAME = "PaleoBytes"
PROGRAM_NAME = "DikeMapper"
PROGRAM_VERSION = "0.0.3"

# Get user profile directory
USER_PROFILE_DIRECTORY = os.path.expanduser('~')

# Define directory structure
DEFAULT_DB_DIRECTORY = os.path.join(USER_PROFILE_DIRECTORY, COMPANY_NAME, PROGRAM_NAME)
DEFAULT_STORAGE_DIRECTORY = os.path.join(DEFAULT_DB_DIRECTORY, "data/")
DEFAULT_LOG_DIRECTORY = os.path.join(DEFAULT_DB_DIRECTORY, "logs/")
DB_BACKUP_DIRECTORY = os.path.join(DEFAULT_DB_DIRECTORY, "backups/")

# Create necessary directories
for directory in [DEFAULT_DB_DIRECTORY, DEFAULT_STORAGE_DIRECTORY, DEFAULT_LOG_DIRECTORY, DB_BACKUP_DIRECTORY]:
    os.makedirs(directory, exist_ok=True)

# Check if WebEngine is available
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    WEB_ENGINE_AVAILABLE = True
except ImportError:
    WEB_ENGINE_AVAILABLE = False

# Set up logging
def setup_logging():
    """Set up logging configuration"""
    # Create log file path with timestamp
    log_file = os.path.join(DEFAULT_LOG_DIRECTORY, f'{PROGRAM_NAME.lower()}_{datetime.datetime.now().strftime("%Y%m%d")}.log')
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Set up file handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    
    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Log initial startup message
    logging.info(f"{PROGRAM_NAME} started. Log file: {log_file}")
    return log_file

# Initialize logging
LOG_FILE = setup_logging()

def debug_print(message, level=1):
    """Print debug messages based on debug level and log them"""
    if KIGAMMapWindow.DEBUG_MODE >= level:
        if level == 0:
            logging.info(message)
        else:
            logging.debug(message)


class ExcelConverterWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.df = None
        self.initUI()
        
    def initUI(self):
        """Initialize the user interface"""
        # Create main layout
        main_layout = QVBoxLayout()
        
        # Create buttons
        self.load_button = QPushButton('Load Excel File', self)
        self.load_button.clicked.connect(self.load_excel_file)
        
        self.save_button = QPushButton('Save to Database', self)
        self.save_button.clicked.connect(self.save_to_database)
        self.save_button.setEnabled(False)  # Initially disabled
        
        # Create table widget
        self.table_widget = QTableWidget(self)
        self.table_widget.setColumnCount(0)
        self.table_widget.setRowCount(0)
        
        # Add widgets to layout
        main_layout.addWidget(self.load_button)
        main_layout.addWidget(self.table_widget)
        main_layout.addWidget(self.save_button)
        
        # Set the layout
        self.setLayout(main_layout)
        
        # Set window properties
        self.setWindowTitle('Excel Data Converter')
        self.resize(800, 600)
    
    def update_table(self):
        if self.df is None:
            return
            
        # Set table dimensions
        self.table_widget.setRowCount(len(self.df))
        self.table_widget.setColumnCount(len(self.df.columns))
        
        # Set headers
        self.table_widget.setHorizontalHeaderLabels(self.df.columns)
        
        # Fill data
        for i in range(len(self.df)):
            for j in range(len(self.df.columns)):
                val = self.df.iloc[i, j]
                if pd.isna(val):
                    item = QTableWidgetItem('')
                else:
                    if isinstance(val, (float, np.float64)):
                        item = QTableWidgetItem(f'{val:.6f}')
                    else:
                        item = QTableWidgetItem(str(val))
                self.table_widget.setItem(i, j, item)
        
        # Adjust column widths
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

    def save_to_database(self):
        """Save the processed data to the database"""
        if self.df is None:
            QMessageBox.warning(self, "No Data", "Please load an Excel file first.")
            return
            
        try:
            # Map Excel columns to database fields
            column_mapping = {
                '기호': 'symbol',
                '지층': 'stratum',
                '대표암상': 'rock_type',
                '시대': 'era',
                '지역': 'map_sheet',
                '주소': 'address',
                '거리 (km)': 'distance',
                '각도': 'angle',
                'X_3857': 'x_coord_1',
                'Y_3857': 'y_coord_1',
                'Calculated_Lat': 'lat_1',
                'Calculated_Lng': 'lng_1'
            }
            required_column = ['거리 (km)', '각도', 'X_3857', 'Y_3857']
            for idx, row in self.df.iterrows():
                if row[required_column].isna().all():
                    self.df = self.df.drop(idx)
            
            # Convert distance from km to meters
            if '거리 (km)' in self.df.columns:
                self.df['거리 (km)'] = self.df['거리 (km)'] * 1000

            # Fix angle calculation
            if '각도' in self.df.columns:
                # Apply the angle transformation row by row
                self.df['각도'] = self.df['각도'].apply(lambda x: (90 - x + 360) % 360 if pd.notnull(x) else x)

            # Create records for each row
            records = []
            for _, row in self.df.iterrows():
                record_data = {}
                for excel_col, db_field in column_mapping.items():
                    if excel_col in self.df.columns:
                        value = row[excel_col]
                        # Convert NaN to None for database
                        if pd.isna(value):
                            value = None
                        record_data[db_field] = value
                
                records.append(DikeRecord(**record_data))
            
            # Bulk insert records
            DikeRecord.bulk_create(records)
            
            QMessageBox.information(self, "Database Save Complete", 
                f"Successfully saved {len(records)} records to the database.")
                
        except Exception as e:
            QMessageBox.critical(self, "Database Save Error", 
                f"Error saving to database: {str(e)}")
            
        self.accept()

    def load_excel_file(self):
        """Import data from an Excel file"""
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Import Geological Data", "", "Excel Files (*.xlsx);;All Files (*)"
        )
        
        if not file_name:
            return  # User canceled
        
        try:
            # waitcursor
            QApplication.setOverrideCursor(Qt.WaitCursor)
            # Read the Excel file
            self.df = pd.read_excel(file_name)
            column_header_text = "지역	기호	지층	대표암상	시대	각도	거리 (km)	주소	색	좌표 X	좌표 Y	사진 이름	코드1 좌표 Lat	코드 1 좌표 Lng"
            column_header_list = column_header_text.split('\t')
            
            # Define column names
            image_col = '사진 이름'
            x_col = '좌표 X'
            y_col = '좌표 Y'
            lat_col = '코드1 좌표 Lat'
            lng_col = '코드 1 좌표 Lng'
            
            # Add new columns for calculated coordinates
            self.df['X_3857'] = np.nan
            self.df['Y_3857'] = np.nan
            self.df['Calculated_Lat'] = np.nan
            self.df['Calculated_Lng'] = np.nan
            self.df['Pixel_X'] = np.nan
            self.df['Pixel_Y'] = np.nan
            self.df['Pixel_Y_Flipped'] = np.nan
            
            # Copy existing lat/lng values to calculated columns
            self.df.loc[self.df[lat_col].notna(), 'Calculated_Lat'] = self.df[lat_col]
            self.df.loc[self.df[lng_col].notna(), 'Calculated_Lng'] = self.df[lng_col]
            
            # Create a transformer from WGS84 (EPSG:4326) to Web Mercator (EPSG:3857)
            transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
            transformer_back = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
            
            # Convert coordinate columns to float, replacing any non-numeric values with NaN
            for col in [x_col, y_col, lat_col, lng_col]:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
            
            # Constants for coordinate conversion
            CM_TO_INCH = 0.393701  # 1 cm = 0.393701 inches
            DPI = 96  # dots per inch
            
            # Process each image group
            image_groups = self.df.groupby(image_col)
            
            # Store transformation parameters for each image
            image_transforms = {}
            
            # First pass: Calculate transformation parameters for each image
            for image_name, group_df in image_groups:
                print(f"\nProcessing image: {image_name}")
                print(f"Number of rows: {len(group_df)}")
                
                # Get rows with lat/lng coordinates
                known_coords = group_df[group_df[lat_col].notna() & group_df[lng_col].notna()]
                
                if len(known_coords) >= 2:
                    print(f"Found {len(known_coords)} rows with known coordinates")
                    
                    # Lists to store coordinates
                    x_pixels = []
                    y_pixels = []
                    x_3857_coords = []
                    y_3857_coords = []
                    max_y = float('-inf')
                    
                    # First pass to find maximum y value
                    for _, row in known_coords.iterrows():
                        y_cm = row[y_col]
                        if pd.notna(y_cm):
                            if isinstance(y_cm, float):
                                y_val = round(y_cm * CM_TO_INCH * DPI)
                            else:
                                y_val = y_cm
                            max_y = max(max_y, y_val)
                    
                    # Process known coordinates
                    for _, row in known_coords.iterrows():
                        try:
                            # Convert cm to pixels if the coordinates are floats
                            x_cm, y_cm = row[x_col], row[y_col]
                            if isinstance(x_cm, float) and isinstance(y_cm, float):
                                x_val = round(x_cm * CM_TO_INCH * DPI)
                                y_val = round(y_cm * CM_TO_INCH * DPI)
                            else:
                                x_val = x_cm
                                y_val = y_cm
                            
                            # Store pixel coordinates
                            self.df.at[row.name, 'Pixel_X'] = x_val
                            self.df.at[row.name, 'Pixel_Y'] = y_val
                            
                            # Invert y coordinate
                            y_val_flipped = max_y - y_val
                            self.df.at[row.name, 'Pixel_Y_Flipped'] = y_val_flipped
                            
                            # Transform lat/lng to EPSG:3857
                            x_3857, y_3857 = transformer.transform(row[lng_col], row[lat_col])
                            self.df.at[row.name, 'X_3857'] = x_3857
                            self.df.at[row.name, 'Y_3857'] = y_3857
                            
                            x_pixels.append(x_val)
                            y_pixels.append(y_val_flipped)
                            x_3857_coords.append(x_3857)
                            y_3857_coords.append(y_3857)
                            
                        except Exception as e:
                            print(f"Error transforming coordinates for row {row.name}: {str(e)}")
                            continue
                    
                    if len(x_pixels) >= 2:
                        # Convert to numpy arrays
                        x_pixels = np.array(x_pixels)
                        y_pixels = np.array(y_pixels)
                        x_3857_coords = np.array(x_3857_coords)
                        y_3857_coords = np.array(y_3857_coords)
                        
                        try:
                            # Calculate x transformation (simple linear regression)
                            A_x = np.vstack([x_pixels, np.ones(len(x_pixels))]).T
                            x_slope, x_intercept = np.linalg.lstsq(A_x, x_3857_coords, rcond=None)[0]
                            
                            # Calculate y transformation (simple linear regression)
                            A_y = np.vstack([y_pixels, np.ones(len(y_pixels))]).T
                            y_slope, y_intercept = np.linalg.lstsq(A_y, y_3857_coords, rcond=None)[0]
                            
                            # Store transformation parameters
                            image_transforms[image_name] = {
                                'max_y': max_y,
                                'x_slope': x_slope,
                                'x_intercept': x_intercept,
                                'y_slope': y_slope,
                                'y_intercept': y_intercept
                            }
                            
                            print(f"\nTransformation parameters for {image_name}:")
                            print(f"X_3857 = {x_slope:.6f} * x_pixel + {x_intercept:.6f}")
                            print(f"Y_3857 = {y_slope:.6f} * y_pixel + {y_intercept:.6f}")
                            
                        except np.linalg.LinAlgError as e:
                            print(f"Error calculating transformation for {image_name}: {str(e)}")
                    else:
                        print(f"Not enough valid coordinates for {image_name}")
                else:
                    print(f"Not enough known coordinates for {image_name}")
            
            # Second pass: Calculate coordinates for all rows
            print("\nCalculating coordinates for all rows...")
            
            for idx, row in self.df.iterrows():
                image_name = row[image_col]
                transform = image_transforms.get(image_name)
                
                if transform is None:
                    print(f"No transformation available for image {image_name}")
                    continue
                
                try:
                    # Convert coordinates
                    x_cm, y_cm = row[x_col], row[y_col]
                    if pd.notna(x_cm) and pd.notna(y_cm):
                        if isinstance(x_cm, float) and isinstance(y_cm, float):
                            x_val = round(x_cm * CM_TO_INCH * DPI)
                            y_val = round(y_cm * CM_TO_INCH * DPI)
                        else:
                            x_val = x_cm
                            y_val = y_cm
                        
                        # Store pixel coordinates if not already stored
                        if pd.isna(self.df.at[idx, 'Pixel_X']):
                            self.df.at[idx, 'Pixel_X'] = x_val
                            self.df.at[idx, 'Pixel_Y'] = y_val
                        
                        # Invert y coordinate
                        y_val_flipped = transform['max_y'] - y_val
                        if pd.isna(self.df.at[idx, 'Pixel_Y_Flipped']):
                            self.df.at[idx, 'Pixel_Y_Flipped'] = y_val_flipped
                        
                        # Calculate EPSG:3857 coordinates
                        x_3857 = transform['x_slope'] * x_val + transform['x_intercept']
                        y_3857 = transform['y_slope'] * y_val_flipped + transform['y_intercept']
                        
                        # Store EPSG:3857 coordinates if not already stored
                        if pd.isna(self.df.at[idx, 'X_3857']):
                            self.df.at[idx, 'X_3857'] = x_3857
                            self.df.at[idx, 'Y_3857'] = y_3857
                        
                        # Calculate and store WGS84 coordinates if not already present
                        if pd.isna(row[lat_col]) or pd.isna(row[lng_col]):
                            lng, lat = transformer_back.transform(x_3857, y_3857)
                            self.df.at[idx, 'Calculated_Lat'] = lat
                            self.df.at[idx, 'Calculated_Lng'] = lng
                        
                except Exception as e:
                    print(f"Error processing row {idx}: {str(e)}")
                    continue
            
            # Update the table with the new data
            self.update_table()

            # restore cursor
            QApplication.restoreOverrideCursor()

            self.save_button.setEnabled(True)
            #self.save_db_button.setEnabled(True)  # Enable database save button
            
            QMessageBox.information(self, "Import Complete", 
                "Data has been loaded and coordinates calculated successfully.")

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Error importing data: {str(e)}")
            # restore cursor
            QApplication.restoreOverrideCursor()
    
    def save_excel_file(self):
        if self.df is None:
            return
            
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save Excel File", "", "Excel Files (*.xlsx);;All Files (*)"
        )
        
        if not file_name:
            return  # User canceled
            
        try:
            # Save the DataFrame to Excel
            self.df.to_excel(file_name, index=False)
            QMessageBox.information(self, "Save Complete", 
                f"Data has been saved to:\n{file_name}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Error saving file: {str(e)}")

class KIGAMMapWindow(QMainWindow):
    """A window to display the geological map from KIGAM website"""
    DEBUG_MODE = 0  # Default: no debugging (0), Basic (1), Verbose (2)
    
    def __init__(self, parent=None):
        """Initialize the main window"""
        super().__init__(parent)
        
        # Show wait cursor during initialization
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            # Initialize settings first
            self.settings = QSettings(COMPANY_NAME, PROGRAM_NAME)
            
            # Initialize database
            self.init_database()
            
            # Initialize UI
            self.initUI()
            
            # Restore window geometry
            self.restore_window_geometry()
            
            # Load saved credentials
            self.load_saved_credentials()
            
        finally:
            # Restore normal cursor
            QApplication.restoreOverrideCursor()
        
    def initUI(self):
        # Initialize settings first
        self.settings = QSettings("PaleoBytes", "DikeMapper")
        
        # Set window title
        self.setWindowTitle(f"{PROGRAM_NAME} v{PROGRAM_VERSION} - KIGAM Geological Map")
        
        # Set default size if no saved geometry exists
        default_geometry = self.settings.value("window_geometry")
        if not default_geometry:
            self.setGeometry(200, 200, 1000, 800)
        
        # Create central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        # Create toolbar
        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)
        
        # Initialize database
        self.init_database()
        
        # Map view position and zoom storage
        self.current_map_center = None
        self.current_map_zoom = None
        
        # Add login controls
        login_layout = QHBoxLayout()
        
        self.email_label = QLabel("Email:")
        self.email_input = QLineEdit()
        self.password_label = QLabel("Password:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.remember_me = QCheckBox("Remember Me")
        self.login_button = QPushButton("Login", self)
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
        
        self.distance_button = QPushButton("Distance")
        self.distance_button.setToolTip("Measure distance between points on the map")
        self.distance_button.clicked.connect(self.activate_distance_tool)
        self.distance_button.setCheckable(True)
        
        self.add_to_table_button = QPushButton("Add to Table")
        self.add_to_table_button.setToolTip("Add current geological information to the table")
        self.add_to_table_button.clicked.connect(self.add_current_info_to_table)
        self.add_to_table_button.setEnabled(False)  # Disabled until we have info
        
        # Add info display as a QLineEdit instead of a large text box
        self.geo_info_label = QLineEdit()
        self.geo_info_label.setReadOnly(True)
        self.geo_info_label.setPlaceholderText("Geological information will appear here")
        self.geo_info_label.setMinimumWidth(200)  # Reduced minimum width
        self.geo_info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Allow horizontal stretching
        
        # Add distance/angle display
        self.measurement_label = QLineEdit()
        self.measurement_label.setReadOnly(True)
        self.measurement_label.setPlaceholderText("Distance and angle measurements")
        self.measurement_label.setMinimumWidth(150)  # Reduced minimum width
        self.measurement_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Allow horizontal stretching
        
        # Add coordinate display with fixed width
        self.coords_label1 = QLabel("Coord1: ")
        self.coords_label1.setMinimumWidth(200)  # Reduced minimum width
        self.coords_label2 = QLabel("Coord2: ")
        self.coords_label2.setMinimumWidth(200)  # Reduced minimum width
        #self.coords_label.setMaximumWidth(300)  # Reduced maximum width
        
        # Create a QHBoxLayout for the tools and set size constraints
        tools_layout.setSizeConstraint(QLayout.SetFixedSize)  # Prevent layout from expanding
        
        # Add widgets with appropriate size policies
        tools_layout.addWidget(self.info_button)
        tools_layout.addWidget(self.distance_button)
        tools_layout.addWidget(self.geo_info_label, 2)  # Stretch factor of 2
        tools_layout.addWidget(self.measurement_label, 1)  # Stretch factor of 1
        tools_layout.addWidget(self.coords_label1)
        tools_layout.addWidget(self.coords_label2)
        tools_layout.addWidget(self.add_to_table_button)
        tools_layout.addStretch(1)  # Add stretch to push other widgets to the right
        
        self.layout.addLayout(tools_layout)
        
        # Create splitter for map and table
        self.splitter = QSplitter(Qt.Vertical)
        self.layout.addWidget(self.splitter, 1)  # Give splitter stretch priority
        
        # Add web view to top part of splitter
        self.web_view_container = QWidget()
        self.web_view_layout = QVBoxLayout(self.web_view_container)
        self.web_view_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add map control buttons (moved here after web_view_layout is created)
        map_controls_layout = QHBoxLayout()
        
        self.pan_left_button = QPushButton("←")
        self.pan_left_button.setToolTip("Pan map to the west")
        self.pan_left_button.clicked.connect(lambda: self.pan_map("west"))
        
        self.pan_right_button = QPushButton("→")
        self.pan_right_button.setToolTip("Pan map to the east")
        self.pan_right_button.clicked.connect(lambda: self.pan_map("east"))
        
        self.pan_up_button = QPushButton("↑")
        self.pan_up_button.setToolTip("Pan map to the north")
        self.pan_up_button.clicked.connect(lambda: self.pan_map("north"))
        
        self.pan_down_button = QPushButton("↓")
        self.pan_down_button.setToolTip("Pan map to the south")
        self.pan_down_button.clicked.connect(lambda: self.pan_map("south"))
        
        map_controls_layout.addWidget(self.pan_left_button)
        map_controls_layout.addWidget(self.pan_right_button)
        map_controls_layout.addWidget(self.pan_up_button)
        map_controls_layout.addWidget(self.pan_down_button)
        
        self.web_view_layout.addLayout(map_controls_layout)
        
        # Create web view with size policy
        self.web_view = QWebEngineView()
        self.web_view.loadFinished.connect(self.on_page_load_finished)
        self.web_view.setMinimumHeight(500)
        self.web_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # Allow the web view to expand
        self.web_view_layout.addWidget(self.web_view)
        self.splitter.addWidget(self.web_view_container)
        
        # Create table view in bottom part of splitter
        self.table_container = QWidget()
        self.table_layout = QVBoxLayout(self.table_container)
        
        # Add table controls
        table_controls_layout = QHBoxLayout()
        
        self.add_to_table_button = QPushButton("Add to Table")
        self.add_to_table_button.setToolTip("Add current geological information to the table")
        self.add_to_table_button.clicked.connect(self.add_current_info_to_table)
        self.add_to_table_button.setEnabled(False)  # Initially disabled until we have data
        
        self.delete_row_button = QPushButton("Delete Selected")
        self.delete_row_button.setToolTip("Delete the selected row from the table")
        self.delete_row_button.clicked.connect(self.delete_selected_row)
        self.delete_row_button.setEnabled(False)  # Initially disabled until a row is selected
        
        self.center_selected_button = QPushButton("Center Selected")
        self.center_selected_button.setToolTip("Center the map on the selected row's coordinates")
        self.center_selected_button.clicked.connect(self.center_map_on_selected)
        self.center_selected_button.setEnabled(False)  # Initially disabled until a row is selected
        
        self.clear_table_button = QPushButton("Clear Table")
        self.clear_table_button.setToolTip("Clear all rows from the table")
        self.clear_table_button.clicked.connect(self.clear_geo_table)
        
        self.import_excel_button = QPushButton("Import Excel", self)
        self.import_excel_button.clicked.connect(self.import_excel_file)
        
        self.export_table_button = QPushButton("Export Table")
        self.export_table_button.setToolTip("Export the table data to a CSV file")
        self.export_table_button.clicked.connect(self.export_geo_table)

        table_controls_layout.addWidget(self.add_to_table_button)
        table_controls_layout.addWidget(self.delete_row_button)
        table_controls_layout.addWidget(self.center_selected_button)
        table_controls_layout.addWidget(self.clear_table_button)
        table_controls_layout.addWidget(self.import_excel_button)
        table_controls_layout.addWidget(self.export_table_button)
        
        self.table_layout.addLayout(table_controls_layout)
        
        # Create the actual table for geological data
        self.geo_table = QTableWidget()
        self.geo_table.setColumnCount(8)
        self.geo_table.setHorizontalHeaderLabels(["기호 (Symbol)", "지층 (Stratum)", 
                                                "대표암상 (Rock Type)", "시대 (Era)", 
                                                "도폭 (Map Sheet)", "주소 (Address)",
                                                "거리 (Distance)", "각도 (Angle)"])
        self.geo_table.horizontalHeader().setStretchLastSection(True)
        self.geo_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Set selection behavior to select entire rows
        self.geo_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.geo_table.setSelectionMode(QTableWidget.SingleSelection)
        
        # Disable editing
        self.geo_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Enable vertical scrollbar
        self.geo_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.geo_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Connect selection changed signal to enable/disable delete button
        self.geo_table.itemSelectionChanged.connect(self.on_table_selection_changed)
        
        # Add double-click handler
        self.geo_table.cellDoubleClicked.connect(self.on_table_double_click)
        
        self.table_layout.addWidget(self.geo_table)
        
        self.splitter.addWidget(self.table_container)
        
        # Set initial splitter sizes (70% map, 30% table)
        self.splitter.setSizes([600, 200])
        
        # Create JavaScript handler for callbacks
        class JSHandler(QObject):
            popupInfoReceived = pyqtSignal(str)
            distanceMeasured = pyqtSignal(str)
        
        self.js_handler = JSHandler()
        self.js_handler.popupInfoReceived.connect(self.handle_popup_info)
        self.js_handler.distanceMeasured.connect(self.handle_distance_measurement)
        
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
        self.current_raw_x = None
        self.current_raw_y = None

        self.previous_lat = None
        self.previous_lng = None
        self.previous_raw_x = None
        self.previous_raw_y = None
        self.wgs_distance = 0
        self.wgs_angle = 0

        # current distance measurement
        self.current_distance_measurement = None

        # current angle measurement
        self.current_angle_measurement = None
        
        # Store the target map URL
        self.target_map_url = "https://data.kigam.re.kr/mgeo/map/main.do?process=geology_50k"
        
        # Load saved credentials if available
        self.load_saved_credentials()
        
        # Load the KIGAM website - updated to the correct login URL
        self.web_view.load(QUrl("https://data.kigam.re.kr/auth/login?redirect=/mgeo/sub01/page02.do"))
    
    def init_database(self):
        """Initialize the database"""
        global DB_PATH
        
        try:
            # Set default database path
            DB_PATH = os.path.join(DEFAULT_DB_DIRECTORY, f"{PROGRAM_NAME.lower()}.db")
            
            # Create database directory if it doesn't exist
            os.makedirs(DEFAULT_DB_DIRECTORY, exist_ok=True)
            
            # Check if database exists
            if os.path.exists(DB_PATH):
                # Create backup directory if it doesn't exist
                backup_dir = os.path.join(DEFAULT_DB_DIRECTORY, 'backups')
                os.makedirs(backup_dir, exist_ok=True)
                
                # Generate today's backup filename
                today = datetime.datetime.now().strftime('%Y%m%d%H')
                backup_filename = f"{PROGRAM_NAME.lower()}_{today}.db"
                backup_path = os.path.join(backup_dir, backup_filename)
                
                # Check if today's backup exists
                if not os.path.exists(backup_path):
                    try:
                        # Copy current database to backup
                        shutil.copy2(DB_PATH, backup_path)
                        logging.info(f"Created database backup: {backup_filename}")
                    except Exception as e:
                        logging.error(f"Failed to create database backup: {str(e)}")
            
            # Initialize the database
            db.init(DB_PATH)
            db.connect()
            
            # Create tables
            db.create_tables([DikeRecord])
            
            # Close the connection
            db.close()
            
            logging.info("Database initialized successfully")
            
        except Exception as e:
            QMessageBox.critical(self, "Database Error", 
                f"Error initializing database: {str(e)}")
            logging.error(f"Database initialization error: {str(e)}")
            self.close()
    
    def load_data_from_database(self):
        """Load data from the database into the table"""
        try:
            # Clear existing table data
            self.geo_table.setRowCount(0)
            
            # Ensure we have enough columns for all data
            if self.geo_table.columnCount() < 17:  # Increased by 1 for ID column
                self.geo_table.setColumnCount(17)
                headers = ["ID", "기호 (Symbol)", "지층 (Stratum)", 
                           "대표암상 (Rock Type)", "시대 (Era)", 
                           "도폭 (Map Sheet)", "주소 (Address)",
                           "거리 (Distance)", "각도 (Angle)",
                           "X 좌표 1", "Y 좌표 1", "위도 (Latitude) 1", "경도 (Longitude) 1",
                           "X 좌표 2", "Y 좌표 2", "위도 (Latitude) 2", "경도 (Longitude) 2"]
                self.geo_table.setHorizontalHeaderLabels(headers)
            
            # Load records from database
            records = DikeRecord.select().order_by(DikeRecord.created_date)
            
            for record in records:
                row = self.geo_table.rowCount()
                self.geo_table.insertRow(row)
                
                # Add ID to table
                self.geo_table.setItem(row, 0, QTableWidgetItem(str(record.id)))
                
                # Add basic information to table
                self.geo_table.setItem(row, 1, QTableWidgetItem(record.symbol or ""))
                self.geo_table.setItem(row, 2, QTableWidgetItem(record.stratum or ""))
                self.geo_table.setItem(row, 3, QTableWidgetItem(record.rock_type or ""))
                self.geo_table.setItem(row, 4, QTableWidgetItem(record.era or ""))
                self.geo_table.setItem(row, 5, QTableWidgetItem(record.map_sheet or ""))
                self.geo_table.setItem(row, 6, QTableWidgetItem(record.address or ""))
                
                # Add distance and angle if available
                try:
                    if record.distance is not None:
                        self.geo_table.setItem(row, 7, QTableWidgetItem(f"{float(record.distance):.1f}m"))
                except (ValueError, TypeError):
                    self.geo_table.setItem(row, 7, QTableWidgetItem(""))
                    
                try:
                    if record.angle is not None:
                        self.geo_table.setItem(row, 8, QTableWidgetItem(f"{float(record.angle):.1f}°"))
                except (ValueError, TypeError):
                    self.geo_table.setItem(row, 8, QTableWidgetItem(""))
                
                # Add first set of coordinates (X1, Y1, Lat1, Lng1)
                try:
                    if record.x_coord_1 is not None:
                        self.geo_table.setItem(row, 9, QTableWidgetItem(f"{float(record.x_coord_1):.3f}"))
                except (ValueError, TypeError):
                    self.geo_table.setItem(row, 9, QTableWidgetItem(""))
                    
                try:
                    if record.y_coord_1 is not None:
                        self.geo_table.setItem(row, 10, QTableWidgetItem(f"{float(record.y_coord_1):.3f}"))
                except (ValueError, TypeError):
                    self.geo_table.setItem(row, 10, QTableWidgetItem(""))
                    
                try:
                    if record.lat_1 is not None:
                        self.geo_table.setItem(row, 11, QTableWidgetItem(f"{float(record.lat_1):.6f}"))
                except (ValueError, TypeError):
                    self.geo_table.setItem(row, 11, QTableWidgetItem(""))
                    
                try:
                    if record.lng_1 is not None:
                        self.geo_table.setItem(row, 12, QTableWidgetItem(f"{float(record.lng_1):.6f}"))
                except (ValueError, TypeError):
                    self.geo_table.setItem(row, 12, QTableWidgetItem(""))
                
                # Add second set of coordinates (X2, Y2, Lat2, Lng2)
                try:
                    if record.x_coord_2 is not None:
                        self.geo_table.setItem(row, 13, QTableWidgetItem(f"{float(record.x_coord_2):.3f}"))
                except (ValueError, TypeError):
                    self.geo_table.setItem(row, 13, QTableWidgetItem(""))
                    
                try:
                    if record.y_coord_2 is not None:
                        self.geo_table.setItem(row, 14, QTableWidgetItem(f"{float(record.y_coord_2):.3f}"))
                except (ValueError, TypeError):
                    self.geo_table.setItem(row, 14, QTableWidgetItem(""))
                    
                try:
                    if record.lat_2 is not None:
                        self.geo_table.setItem(row, 15, QTableWidgetItem(f"{float(record.lat_2):.6f}"))
                except (ValueError, TypeError):
                    self.geo_table.setItem(row, 15, QTableWidgetItem(""))
                    
                try:
                    if record.lng_2 is not None:
                        self.geo_table.setItem(row, 16, QTableWidgetItem(f"{float(record.lng_2):.6f}"))
                except (ValueError, TypeError):
                    self.geo_table.setItem(row, 16, QTableWidgetItem(""))
            
            # Adjust column widths
            self.geo_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Error loading data from database: {str(e)}")
        
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
            
            # Restore previous map position and zoom after a short delay
            # to allow the map to fully initialize
            QTimer.singleShot(2000, self.restore_map_state)
            
            # Load geological data from database after map loading is complete
            QTimer.singleShot(2500, self.load_data_from_database)
    
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
            self.geo_info_label.setStyleSheet("background-color: rgba(255, 255, 200, 220); padding: 5px; border-radius: 3px;")
            self.geo_info_label.setText("Activating info tool... please wait")
            
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
            self.geo_info_label.setStyleSheet("background-color: rgba(255, 255, 255, 220); padding: 5px; border-radius: 3px;")
            self.geo_info_label.setText("Info tool deactivated")
            
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
            self.geo_info_label.setStyleSheet("background-color: rgba(200, 255, 200, 220); padding: 5px; border-radius: 3px;")
            self.geo_info_label.setText("Info tool activated - Click on the map to view geological information")
            
            # Check if we have monitoring set up
            self.web_view.page().runJavaScript(
                """window._kigamMonitorSetup ? "Monitoring active" : "Monitoring not active";""",
                lambda status: self.check_monitoring_status(status)
            )
        else:
            self.info_button.setChecked(False)
            self.info_tool_active = False
            self.statusBar().showMessage(f"Could not activate info tool: {result}", 5000)
            self.geo_info_label.setStyleSheet("background-color: rgba(255, 200, 200, 220); padding: 5px; border-radius: 3px;")
            self.geo_info_label.setText("Error: Could not find the info button on the map")
            
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
            
            // Add distance measurement handler
            window.qt.distanceMeasured = function(distance) {
                console.log('Distance measured:', distance);
                window._lastDistanceMeasurement = distance;
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
        
        # Add distance measurement monitoring with click/doubleclick handling
        distance_monitor = """
        (function() {
            console.log('Setting up distance measurement monitoring');
            
            // Track click timing for double click detection
            window._lastClickTime = 0;
            window._clickTimeout = null;
            window._measurementStarted = false;

            // Function to check for static distance tooltip
            function checkForStaticTooltip() {
                var staticTooltip = document.querySelector('.ol-overlaycontainer-stopevent .tooltip.tooltip-static');
                if (staticTooltip && staticTooltip.style.display !== 'none') {
                    var content = staticTooltip.textContent.trim();
                    console.log('Found static tooltip:', content);
                    if (content && window.jsCallback) {
                        window.jsCallback.handle_distance_measurement(content);
                    }
                }
            }

            // Find the map instance
            var mapElement = document.querySelector('.ol-viewport');
            if (mapElement) {
                // Add click handler to detect single/double clicks
                mapElement.addEventListener('click', function(e) {
                    var currentTime = new Date().getTime();
                    var timeDiff = currentTime - window._lastClickTime;
                    
                    // Clear any existing timeout
                    if (window._clickTimeout) {
                        clearTimeout(window._clickTimeout);
                    }
                    
                    if (timeDiff < 300) { // Double click threshold
                        console.log('Double click detected - ending measurement');
                        // This is a double click - end measurement
                        if (window._measurementStarted) {
                            checkForStaticTooltip();
                            window._measurementStarted = false;
                        }
                    } else {
                        // This might be a single click - wait to see if it's part of a double click
                        window._clickTimeout = setTimeout(function() {
                            console.log('Single click processed - starting measurement');
                            window._measurementStarted = true;
                        }, 300);
                    }
                    
                    window._lastClickTime = currentTime;
                });
            }

            // Set up polling interval for the static tooltip
            if (!window._distanceMonitorInterval) {
                window._distanceMonitorInterval = setInterval(checkForStaticTooltip, 500);
                console.log('Distance monitor interval set up');
            }

            return "Distance measurement monitoring set up with click handling";
        })();
        """
        
        debug_print("Setting up distance measurement monitoring", 0)
        self.web_view.page().runJavaScript(distance_monitor, lambda result: debug_print(f"Distance monitoring setup: {result}", 0))
    
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
            self.geo_info_label.setStyleSheet("background-color: rgba(200, 255, 200, 220); padding: 5px; border-radius: 3px;")
        else:
            self.statusBar().showMessage(f"Map monitoring issue: {result}", 5000)
            self.geo_info_label.setStyleSheet("background-color: rgba(255, 240, 200, 220); padding: 5px; border-radius: 3px;")
            self.geo_info_label.setText(f"Warning: Map monitoring setup issue: {result}")
    
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
                    self.geo_info_label.setText("Info tool active and monitoring ready - Click on the map to view information")
                    self.geo_info_label.setStyleSheet("background-color: rgba(200, 255, 200, 220); padding: 5px; border-radius: 3px;")
                else:
                    problems = []
                    if not status['monitorSetup']: problems.append("Monitor not set up")
                    if not status['intervalActive']: problems.append("Check interval not active")
                    if not status['popupHandler']: problems.append("Popup handler missing")
                    if not status['jsCallback']: problems.append("JS callback missing")
                    
                    self.geo_info_label.setText(f"Warning: Monitoring has issues: {', '.join(problems)}")
                    self.geo_info_label.setStyleSheet("background-color: rgba(255, 240, 200, 220); padding: 5px; border-radius: 3px;")
            
        except json.JSONDecodeError:
            debug_print(f"Could not parse verification result: {result}", 0)
            
    def handle_popup_info(self, content):
        """Handle the geological information from a map popup"""
        debug_print(f"Popup information received: {content}", 0)
        
        if content:
            # Store the current content for adding to table
            self.current_geo_info = content
            
            # Parse the information
            info_dict = self.parse_geological_info(content)
            
            if info_dict:
                # Format a compact display string with only geological information
                compact_info = f"Symbol: {info_dict.get('symbol', 'N/A')} | Rock: {info_dict.get('rock_type', 'N/A')}"
                
                # Update the geological info label
                self.geo_info_label.setText(compact_info)
                self.geo_info_label.setStyleSheet("background-color: rgba(220, 255, 220, 240); padding: 2px; border-radius: 3px;")
            else:
                self.geo_info_label.setText("Could not parse geological information")
                self.geo_info_label.setStyleSheet("background-color: rgba(255, 240, 200, 220); padding: 2px; border-radius: 3px;")
            
            # Enable the add to table button if distance measurement is also available
            self.update_add_to_table_button_state()
            
            # Flash the label briefly
            current_style = self.geo_info_label.styleSheet()
            self.geo_info_label.setStyleSheet("background-color: rgba(200, 255, 200, 240); padding: 2px; border-radius: 3px;")
            QTimer.singleShot(300, lambda: self.geo_info_label.setStyleSheet(current_style))
        else:
            self.current_geo_info = None
            self.update_add_to_table_button_state()
            self.geo_info_label.setText("No geological information found")
            self.geo_info_label.setStyleSheet("background-color: rgba(255, 240, 200, 220); padding: 2px; border-radius: 3px;")
            self.statusBar().showMessage("No information found at clicked location", 3000)
            
    def handle_distance_measurement(self, distance_text):
        """Handle a distance measurement"""
        debug_print(f"Distance measurement received: {distance_text}", 0)
        
        # Extract distance and angle from the text
        # Example format: "거리: 289.69 m | 각도: 256.7°" or similar
        distance_match = re.search(r'(\d+\.?\d*)\s*m', distance_text)
        angle_match = re.search(r'(\d+\.?\d*)\s*°', distance_text)
        
        if distance_match:
            self.current_distance_measurement = distance_match.group(1)
            debug_print(f"Extracted distance: {self.current_distance_measurement} m", 0)
        
        if angle_match:
            self.current_angle_measurement = angle_match.group(1)
            debug_print(f"Extracted angle: {self.current_angle_measurement}°", 0)
            
        # Update the measurement label
        if hasattr(self, 'current_distance_measurement') and self.current_distance_measurement is not None:
            measurement_text = f"Distance: {self.current_distance_measurement} m"
            if hasattr(self, 'current_angle_measurement') and self.current_angle_measurement is not None:
                measurement_text += f" | Angle: {self.current_angle_measurement}°"
            self.measurement_label.setText(measurement_text)
            self.measurement_label.setStyleSheet("background-color: rgba(220, 220, 255, 240); padding: 2px; border-radius: 3px;")
            
            # Flash the label briefly
            current_style = self.measurement_label.styleSheet()
            self.measurement_label.setStyleSheet("background-color: rgba(200, 200, 255, 240); padding: 2px; border-radius: 3px;")
            QTimer.singleShot(300, lambda: self.measurement_label.setStyleSheet(current_style))
        
        # Check if we should enable the add to table button
        self.update_add_to_table_button_state()
        
        # If we have current geological info, redisplay it
        if hasattr(self, 'current_geo_info') and self.current_geo_info:
            self.handle_popup_info(self.current_geo_info)
            
    def update_add_to_table_button_state(self):
        """Update the state of the Add to Table button based on available data"""
        has_geo_info = hasattr(self, 'current_geo_info') and self.current_geo_info is not None
        has_distance = hasattr(self, 'distance_measurement') and self.distance_measurement is not None
        
        debug_print(f"Updating Add to Table button state - Geo info: {has_geo_info}, Distance: {has_distance}", 0)
        
        # Enable the button if we have both geological info and distance measurement
        self.add_to_table_button.setEnabled(has_geo_info and has_distance)
        
        if has_geo_info and has_distance:
            self.add_to_table_button.setStyleSheet("background-color: rgba(200, 255, 200, 240);")
            debug_print("Add to Table button enabled", 0)
        else:
            self.add_to_table_button.setStyleSheet("")
            debug_print("Add to Table button disabled", 0)
    
    def update_coordinates(self):
        """Update the coordinate display with WGS84 coordinates"""
        debug_print(f"Updating coordinates display", 0)
        
        # Format the coordinate display
        if self.current_lat is not None and self.current_lng is not None:
            self.coords_label1.setText(f"Curr.: Lat/Lng ({self.current_lat:.6f},{self.current_lng:.6f}) / Raw ({self.current_raw_x:.3f},{self.current_raw_y:.3f})")
        else:
            self.coords_label1.setText("Curr.: N/A")
        if self.previous_lat is not None and self.previous_lng is not None:
            self.coords_label2.setText(f"Prev.: Lat/Lng ({self.previous_lat:.6f},{self.previous_lng:.6f}) / Raw ({self.previous_raw_x:.3f},{self.previous_raw_y:.3f})")
        else:
            self.coords_label2.setText("Prev.: N/A")
        
        # Check if we have geological information to add to the table
        if self.current_geo_info:
            self.add_to_table_button.setEnabled(True)
        
        if self.current_lat is not None and self.current_lng is not None and self.previous_lat is not None and self.previous_lng is not None:
            self.statusBar().showMessage(f"Coords: {self.current_lat:.6f}, {self.current_lng:.6f} / {self.previous_lat:.6f}, {self.previous_lng:.6f}", 2000)
        else:
            self.statusBar().showMessage("No coords available.", 2000)
    
    def add_current_info_to_table(self):
        """Add current geological information to the table"""
        if not self.current_geo_info:
            QMessageBox.warning(self, "No Data", "No geological information available to add")
            return
        
        # Parse the information to extract fields
        info_dict = self.parse_geological_info(self.current_geo_info)
        
        if not info_dict:
            QMessageBox.warning(self, "Parse Error", "Could not parse geological information")
            return
            
        try:
            # Extract numeric values for database storage
            distance_value = None
            angle_value = None
            
            # Convert distance and angle to float values
            if hasattr(self, 'current_distance_measurement') and self.current_distance_measurement is not None:
                try:
                    distance_value = float(self.current_distance_measurement)
                except (ValueError, TypeError):
                    distance_value = None
                    
            if hasattr(self, 'current_angle_measurement') and self.current_angle_measurement is not None:
                try:
                    angle_value = float(self.current_angle_measurement)
                except (ValueError, TypeError):
                    angle_value = None
            
            # Prepare coordinate values (rounded appropriately)
            prev_x = round(float(self.previous_raw_x), 3) if hasattr(self, 'previous_raw_x') and self.previous_raw_x is not None else None
            prev_y = round(float(self.previous_raw_y), 3) if hasattr(self, 'previous_raw_y') and self.previous_raw_y is not None else None
            prev_lat = round(float(self.previous_lat), 6) if hasattr(self, 'previous_lat') and self.previous_lat is not None else None
            prev_lng = round(float(self.previous_lng), 6) if hasattr(self, 'previous_lng') and self.previous_lng is not None else None
            
            curr_x = round(float(self.current_raw_x), 3) if hasattr(self, 'current_raw_x') and self.current_raw_x is not None else None
            curr_y = round(float(self.current_raw_y), 3) if hasattr(self, 'current_raw_y') and self.current_raw_y is not None else None
            curr_lat = round(float(self.current_lat), 6) if hasattr(self, 'current_lat') and self.current_lat is not None else None
            curr_lng = round(float(self.current_lng), 6) if hasattr(self, 'current_lng') and self.current_lng is not None else None
            
            # Validate required data
            if not (prev_lat and prev_lng and curr_lat and curr_lng):
                QMessageBox.warning(self, "Invalid Data", "Missing coordinate information")
                return
            
            # Connect to database and create record
            if db.is_closed():
                db.connect()

            map_sheet = info_dict.get('map_sheet', '')
            if '[' in map_sheet:
                map_sheet = map_sheet.split('[')[0]
            
            # Create database record
            record = DikeRecord.create(
                symbol=info_dict.get('symbol', ''),
                stratum=info_dict.get('stratum', ''),
                rock_type=info_dict.get('rock_type', ''),
                era=info_dict.get('era', ''),
                map_sheet=map_sheet,
                address=info_dict.get('address', ''),
                distance=distance_value,
                angle=angle_value,
                x_coord_1=prev_x,
                y_coord_1=prev_y,
                lat_1=prev_lat,
                lng_1=prev_lng,
                x_coord_2=curr_x,
                y_coord_2=curr_y,
                lat_2=curr_lat,
                lng_2=curr_lng
            )
            
            debug_print(f"Created database record with ID: {record.id}", 0)
            
            # Now add to table with the database ID
            row_position = self.geo_table.rowCount()
            self.geo_table.insertRow(row_position)
            
            # Add ID to first column
            self.geo_table.setItem(row_position, 0, QTableWidgetItem(str(record.id)))
            
            # Add the extracted information to the cells
            self.geo_table.setItem(row_position, 1, QTableWidgetItem(info_dict.get('symbol', '')))
            self.geo_table.setItem(row_position, 2, QTableWidgetItem(info_dict.get('stratum', '')))
            self.geo_table.setItem(row_position, 3, QTableWidgetItem(info_dict.get('rock_type', '')))
            self.geo_table.setItem(row_position, 4, QTableWidgetItem(info_dict.get('era', '')))
            self.geo_table.setItem(row_position, 5, QTableWidgetItem(map_sheet))
            self.geo_table.setItem(row_position, 6, QTableWidgetItem(info_dict.get('address', '')))
            
            # Add distance and angle with units
            if distance_value is not None:
                self.geo_table.setItem(row_position, 7, QTableWidgetItem(f"{distance_value:.1f}m"))
            if angle_value is not None:
                self.geo_table.setItem(row_position, 8, QTableWidgetItem(f"{angle_value:.1f}°"))
            
            # Add coordinates
            if prev_x is not None:
                self.geo_table.setItem(row_position, 9, QTableWidgetItem(f"{prev_x:.3f}"))
            if prev_y is not None:
                self.geo_table.setItem(row_position, 10, QTableWidgetItem(f"{prev_y:.3f}"))
            if prev_lat is not None:
                self.geo_table.setItem(row_position, 11, QTableWidgetItem(f"{prev_lat:.6f}"))
            if prev_lng is not None:
                self.geo_table.setItem(row_position, 12, QTableWidgetItem(f"{prev_lng:.6f}"))
            
            if curr_x is not None:
                self.geo_table.setItem(row_position, 13, QTableWidgetItem(f"{curr_x:.3f}"))
            if curr_y is not None:
                self.geo_table.setItem(row_position, 14, QTableWidgetItem(f"{curr_y:.3f}"))
            if curr_lat is not None:
                self.geo_table.setItem(row_position, 15, QTableWidgetItem(f"{curr_lat:.6f}"))
            if curr_lng is not None:
                self.geo_table.setItem(row_position, 16, QTableWidgetItem(f"{curr_lng:.6f}"))
            
            # Select the new row
            self.geo_table.selectRow(row_position)
            
            # Show confirmation
            self.statusBar().showMessage(f"Added record with ID {record.id} to database and table", 3000)
            
            # Reset tool states and current data
            self.reset_tool_states()
            
        except Exception as e:
            debug_print(f"Error adding data: {str(e)}", 0)
            QMessageBox.warning(self, "Error", f"Failed to add data: {str(e)}")
        finally:
            if not db.is_closed():
                db.close()
    
    def reset_tool_states(self):
        """Reset all tool states and current data after adding to table"""
        # Reset info tool
        if self.info_button.isChecked():
            self.info_button.setChecked(False)
            self.info_tool_active = False
            self.geo_info_label.setText("")
            self.geo_info_label.setStyleSheet("background-color: rgba(255, 255, 255, 220); padding: 2px; border-radius: 3px;")
        
        # Reset distance tool
        if self.distance_button.isChecked():
            self.distance_button.setChecked(False)
            self.distance_tool_active = False
            self.measurement_label.setText("")
            self.measurement_label.setStyleSheet("background-color: rgba(255, 255, 255, 220); padding: 2px; border-radius: 3px;")
            
            # Deactivate the map's distance measurement button
            self.web_view.page().runJavaScript(
                """
                (function() {
                    var distanceButton = document.querySelector('a.btn_distance, a.btn_distance.active');
                    if (distanceButton) {
                        distanceButton.click();
                        console.log('Deactivated map distance button');
                    }
                })();
                """,
                lambda result: debug_print("Map distance button deactivated", 0)
            )
        
        # Reset current data
        self.current_lat = None
        self.current_lng = None
        self.previous_lat = None
        self.previous_lng = None
        self.current_raw_x = None
        self.current_raw_y = None
        self.previous_raw_x = None
        self.previous_raw_y = None
        self.current_geo_info = None
        self.current_distance_measurement = None
        self.current_angle_measurement = None
        
        # Update UI
        self.update_coordinates()
        self.add_to_table_button.setEnabled(False)
    
    def clear_geo_table(self):
        """Clear all rows from the geological data table and the database"""
        if self.geo_table.rowCount() > 0:
            reply = QMessageBox.question(
                self, 'Confirm Clear', 
                'Are you sure you want to clear all geological data? This will delete all records from the database.',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Clear the table
                self.geo_table.setRowCount(0)
                
                # Clear the database
                try:
                    if db.is_closed():
                        db.connect()
                    DikeRecord.delete().execute()
                    debug_print("All records deleted from database", 0)
                except Exception as e:
                    debug_print(f"Error clearing database: {str(e)}", 0)
                    QMessageBox.warning(self, "Database Error", f"Error clearing database: {str(e)}")
                finally:
                    if not db.is_closed():
                        db.close()
                
                self.statusBar().showMessage("Table and database cleared", 3000)
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


    def calculate_wgs84_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate geodesic (real surface) distance between two points in WGS84.
        
        Parameters:
            lat1, lon1: Latitude and longitude of point A
            lat2, lon2: Latitude and longitude of point B
            
        Returns:
            Distance in meters (float)
        """

        if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
            return 0, 0

        point_a = (lat1, lon1)
        point_b = (lat2, lon2)

        distance = geodesic(point_a, point_b).meters
        # calculate angle
        angle = math.atan2(lat2 - lat1, lon2 - lon1)
        angle = math.degrees(angle)
        angle = 90 - angle
        if angle < 0:
            angle += 360

        return distance, angle

    def handle_coordinate_polling(self, result):
        """Handle the results of coordinate polling"""
        if not result or isinstance(result, bool):
            return
        
        try:
            # Decode the result from JSON
            data = json.loads(result)
            debug_print(f"Received coordinate polling result: {data}", 0)
            
            # If we have raw coordinates, update the raw coordinate display
            if 'raw' in data :

                self.previous_raw_x = self.current_raw_x
                self.previous_raw_y = self.current_raw_y
                self.previous_lat = self.current_lat if hasattr(self, 'current_lat') else None
                self.previous_lng = self.current_lng if hasattr(self, 'current_lng') else None

                self.current_raw_x = data['raw'][0]
                self.current_raw_y = data['raw'][1]
                self.current_projection = data.get('projection', '')
                self.current_lat = data['lat']
                self.current_lng = data['lng']
                self.update_coordinates()
                #self.update_raw_coordinates(data['raw'], data.get('projection', ''))
    

                # Calculate the distance
                self.wgs_distance, self.wgs_angle = self.calculate_wgs84_distance(
                    self.previous_lat, self.previous_lng,
                    self.current_lat, self.current_lng
                )
                    
                debug_print(f"Calculated WGS84 distance: {self.wgs_distance} meters", 0)
                                
                self.current_angle_measurement = f"{self.wgs_angle:.1f}"
                self.current_distance_measurement = f"{self.wgs_distance:.1f}"
                            
                debug_print(f"Distance measurement: {self.current_distance_measurement} m at {self.current_angle_measurement}°", 0)
                
                # Update measurement display
                measurement_text = f"Distance: {self.current_distance_measurement} m | Angle: {self.current_angle_measurement}°"
                self.measurement_label.setText(measurement_text)
                self.measurement_label.setStyleSheet("background-color: rgba(220, 220, 255, 240); padding: 2px; border-radius: 3px;")
                
                # Flash the label
                current_style = self.measurement_label.styleSheet()
                self.measurement_label.setStyleSheet("background-color: rgba(200, 200, 255, 240); padding: 2px; border-radius: 3px;")
                QTimer.singleShot(300, lambda: self.measurement_label.setStyleSheet(current_style))
                                    
            
            
            # Check for info popup content
            if 'popup_content' in data and data['popup_content']:
                popup_content = data['popup_content']
                self.handle_popup_info(popup_content)
            
            # Check for distance measurement
            if 'distance_measurement' in data and data['distance_measurement']:
                distance_text = data['distance_measurement']
                self.handle_distance_measurement(distance_text)

            # Update the button state after processing distance
            self.update_add_to_table_button_state()
            
        except Exception as e:
            debug_print(f"Error processing polling result: {str(e)}", 0)
            import traceback
            debug_print(traceback.format_exc(), 0)
    
    def activate_distance_tool(self, checked):
        """Activate the distance measurement tool on the map"""
        # Update the distance tool state
        self.distance_tool_active = checked
        
        if checked:
            # Uncheck the info button if it's checked
            if self.info_button.isChecked():
                self.info_button.setChecked(False)
                self.info_tool_active = False
            
            self.current_distance_measurement = None
            self.current_angle_measurement = None
            self.current_raw_x = None
            self.current_raw_y = None
            self.current_lat = None
            self.current_lng = None
            self.previous_raw_x = None
            self.previous_raw_y = None
            self.previous_lat = None
            self.previous_lng = None
            
            debug_print(f"Distance tool activated", 0)
            self.statusBar().showMessage("Distance tool activated. Click first point to start, click second point to capture distance.", 5000)
            
            # Update JavaScript state
            self.web_view.page().runJavaScript(
                """
                window._distanceToolActive = true;
                window._distanceMeasurementState = {
                    started: false,
                    startPoint: null
                };
                """,
                lambda result: debug_print("Distance tool state initialized", 0)
            )
            
            # Find and click the distance button in the map interface
            script = """
            (function() {
                console.log('Searching for distance button...');
                
                // Try to find the specific distance button
                var distanceButton = document.querySelector('a.btn_distance, a.btn_distance.active, a.btn_shape[class*="distance"]');
                
                if (!distanceButton) {
                    console.log('Specific distance button not found, trying more general selectors');
                    distanceButton = document.querySelector('.left_btn a[href*="javascript:void(0)"] img[src*="distance"]');
                }
                
                if (!distanceButton) {
                    console.log('Still not found, trying by image alt text');
                    var images = document.querySelectorAll('img');
                    for (var i = 0; i < images.length; i++) {
                        if (images[i].alt && (images[i].alt.includes('거리') || images[i].alt.includes('distance'))) {
                            distanceButton = images[i].parentElement;
                            console.log('Found distance button by image alt text');
                            break;
                        }
                    }
                }
                
                if (distanceButton) {
                    console.log('Found distance button:', distanceButton.outerHTML.substring(0, 100));
                    // Save the element globally for debugging
                    window._distanceButton = distanceButton;
                    
                    // Click it!
                    distanceButton.click();
                    
                    // Check if it has the "active" class after clicking
                    if (distanceButton.classList.contains('active')) {
                        console.log('Distance button has active class - this is good');
                    } else {
                        console.log('Distance button does not have active class - attempting to add it');
                        distanceButton.classList.add('active');
                    }
                    
                    return "Distance tool activated: " + distanceButton.outerHTML.substring(0, 50);
                }
                
                return "Could not find distance measurement button";
            })();
            """
            
            debug_print("Injecting JavaScript to activate distance button", 0)
            self.web_view.page().runJavaScript(script, self.handle_distance_tool_activation)
        else:
            debug_print("Distance tool deactivated", 0)
            self.statusBar().showMessage("Distance tool deactivated", 3000)
            
            # Reset JavaScript state
            self.web_view.page().runJavaScript(
                """
                window._distanceToolActive = false;
                window._distanceMeasurementState = {
                    started: false,
                    startPoint: null
                };
                if (window._distanceButton) {
                    window._distanceButton.click();
                    window._distanceButton.classList.remove('active');
                    console.log('Removed active class from distance button');
                }
                """,
                lambda result: debug_print("Distance tool deactivated in JavaScript", 0)
            )
    
    def handle_distance_tool_activation(self, result):
        """Handle the result of activating the distance tool"""
        debug_print(f"Distance tool activation result: {result}", 0)
        
        if "activated" in result.lower():
            self.statusBar().showMessage("Distance tool activated. Click points on the map to measure distance.", 5000)
        else:
            self.distance_button.setChecked(False)
            self.distance_tool_active = False
            self.statusBar().showMessage(f"Could not activate distance tool: {result}", 5000)
            
            QMessageBox.warning(
                self,
                "Distance Tool Activation Failed",
                f"Could not find the distance measurement button on the map. Result: {result}\n\n"
                "Try these options:\n"
                "1. Click the distance measurement icon on the map manually\n"
                "2. Make sure the map is fully loaded\n"
                "3. Check if the map interface has a distance measurement button"
            )

    def handle_distance_measurement(self, distance_text):
        """Handle a distance measurement"""
        debug_print(f"Distance measurement received: {distance_text}", 0)
        
        # Extract distance and angle from the text
        # Example format: "거리: 289.69 m | 각도: 256.7°" or similar
        distance_match = re.search(r'(\d+\.?\d*)\s*m', distance_text)
        angle_match = re.search(r'(\d+\.?\d*)\s*°', distance_text)
        
        if distance_match:
            self.current_distance_measurement = distance_match.group(1)
            debug_print(f"Extracted distance: {self.current_distance_measurement} m", 0)
        
        if angle_match:
            self.current_angle_measurement = angle_match.group(1)
            debug_print(f"Extracted angle: {self.current_angle_measurement}°", 0)
            
        # Update the measurement label
        if hasattr(self, 'current_distance_measurement') and self.current_distance_measurement is not None:
            measurement_text = f"Distance: {self.current_distance_measurement} m"
            if hasattr(self, 'current_angle_measurement') and self.current_angle_measurement is not None:
                measurement_text += f" | Angle: {self.current_angle_measurement}°"
            self.measurement_label.setText(measurement_text)
            self.measurement_label.setStyleSheet("background-color: rgba(220, 220, 255, 240); padding: 2px; border-radius: 3px;")
            
            # Flash the label briefly
            current_style = self.measurement_label.styleSheet()
            self.measurement_label.setStyleSheet("background-color: rgba(200, 200, 255, 240); padding: 2px; border-radius: 3px;")
            QTimer.singleShot(300, lambda: self.measurement_label.setStyleSheet(current_style))
        
        # Check if we should enable the add to table button
        self.update_add_to_table_button_state()
        
        # If we have current geological info, redisplay it
        if hasattr(self, 'current_geo_info') and self.current_geo_info:
            self.handle_popup_info(self.current_geo_info)
            
    def update_add_to_table_button_state(self):
        """Update the state of the Add to Table button based on available data"""
        has_geo_info = hasattr(self, 'current_geo_info') and self.current_geo_info is not None
        has_distance = hasattr(self, 'current_distance_measurement') and self.current_distance_measurement is not None
        
        debug_print(f"Updating Add to Table button state - Geo info: {has_geo_info}, Distance: {has_distance}", 0)
        
        # Enable the button if we have both geological info and distance measurement
        self.add_to_table_button.setEnabled(has_geo_info and has_distance)
        
        if has_geo_info and has_distance:
            self.add_to_table_button.setStyleSheet("background-color: rgba(200, 255, 200, 240);")
            debug_print("Add to Table button enabled", 0)
        else:
            self.add_to_table_button.setStyleSheet("")
            debug_print("Add to Table button disabled", 0)
    
    def pan_map(self, direction):
        """Pan the map in the specified direction
        
        Args:
            direction (str): The direction to pan the map - 'north', 'south', 'east', or 'west'
        """
        debug_print(f"Panning map {direction}", 0)
        
        # Calculate pan distance based on current view
        script = f"""
        (function() {{
            try {{
                // First, try to find the map object
                var map = null;
                
                // Check for global map variable
                if (window.map && typeof window.map.getView === 'function') {{
                    map = window.map;
                }} else {{
                    // Look for map in global variables
                    for (var key in window) {{
                        try {{
                            if (typeof window[key] === 'object' && window[key] !== null) {{
                                var obj = window[key];
                                if (typeof obj.getView === 'function' && 
                                    typeof obj.getTargetElement === 'function') {{
                                    map = obj;
                                    break;
                                }}
                            }}
                        }} catch (e) {{}}
                    }}
                }}
                
                if (!map) {{
                    return "Map object not found";
                }}
                
                // Get the current view
                var view = map.getView();
                if (!view) {{
                    return "Map view not found";
                }}
                
                // Get the current center
                var center = view.getCenter();
                if (!center) {{
                    return "Map center not found";
                }}
                
                // Get the current resolution (used to calculate pan distance)
                var resolution = view.getResolution();
                if (!resolution) {{
                    resolution = 100; // Default value if resolution can't be determined
                }}
                
                // Calculate pan distance (about 20% of the viewport)
                var mapSize = map.getSize();
                var panDistance = resolution * (mapSize ? Math.min(mapSize[0], mapSize[1]) * 0.2 : 200);
                
                // Create new center based on direction
                var newCenter = center.slice();
                switch ("{direction}") {{
                    case "north":
                        newCenter[1] += panDistance;
                        break;
                    case "south":
                        newCenter[1] -= panDistance;
                        break;
                    case "east":
                        newCenter[0] += panDistance;
                        break;
                    case "west":
                        newCenter[0] -= panDistance;
                        break;
                }}
                
                // Pan to the new center
                view.setCenter(newCenter);
                
                return "Map panned {direction} successfully";
            }} catch (e) {{
                console.error("Error panning map:", e);
                return "Error panning map: " + e.message;
            }}
        }})();
        """
        
        self.web_view.page().runJavaScript(script, lambda result: self.handle_pan_result(result, direction))
    
    def handle_pan_result(self, result, direction):
        """Handle the result of panning the map"""
        debug_print(f"Pan result: {result}", 0)
        
        if "successfully" in result:
            self.statusBar().showMessage(f"Map panned {direction}", 2000)
        else:
            self.statusBar().showMessage(f"Error panning map: {result}", 3000)
            
            # If we couldn't find the map, try a fallback approach
            if "not found" in result:
                fallback_script = f"""
                (function() {{
                    try {{
                        // Fallback approach - find the OpenLayers viewport and simulate pan via drag event
                        var viewport = document.querySelector('.ol-viewport');
                        if (!viewport) {{
                            return "Viewport not found";
                        }}
                        
                        // Calculate drag distance and direction
                        var width = viewport.clientWidth;
                        var height = viewport.clientHeight;
                        var startX = width / 2;
                        var startY = height / 2;
                        var endX = startX;
                        var endY = startY;
                        
                        // Set end position based on direction
                        switch ("{direction}") {{
                            case "north":
                                endY = startY + height * 0.2;
                                break;
                            case "south":
                                endY = startY - height * 0.2;
                                break;
                            case "east":
                                endX = startX - width * 0.2;
                                break;
                            case "west":
                                endX = startX + width * 0.2;
                                break;
                        }}
                        
                        // Create and dispatch mouse events to simulate drag
                        function createMouseEvent(type, x, y) {{
                            var event = new MouseEvent(type, {{
                                bubbles: true,
                                cancelable: true,
                                view: window,
                                clientX: x,
                                clientY: y
                            }});
                            return event;
                        }}
                        
                        // Simulate mousedown
                        viewport.dispatchEvent(createMouseEvent('mousedown', startX, startY));
                        
                        // Simulate mousemove
                        viewport.dispatchEvent(createMouseEvent('mousemove', endX, endY));
                        
                        // Simulate mouseup
                        viewport.dispatchEvent(createMouseEvent('mouseup', endX, endY));
                        
                        return "Map panned using fallback method";
                    }} catch (e) {{
                        console.error("Error in fallback pan:", e);
                        return "Fallback pan failed: " + e.message;
                    }}
                }})();
                """
                
                self.web_view.page().runJavaScript(
                    fallback_script, 
                    lambda result: debug_print(f"Fallback pan result: {result}", 0)
                )

    def closeEvent(self, event):
        """Override closeEvent to save window state and map position"""
        # Save window geometry
        self.settings.setValue("window_geometry", self.saveGeometry())
        
        # Save map position and zoom level before closing
        self.save_map_state()
        event.accept()
        
    def save_map_state(self):
        """Save the current map center position and zoom level"""
        script = """
        (function() {
            try {
                // Find the map object
                var map = null;
                if (window.map && typeof window.map.getView === 'function') {
                    map = window.map;
                } else {
                    // Search for the map in global variables
                    for (var key in window) {
                        try {
                            if (typeof window[key] === 'object' && window[key] !== null) {
                                var obj = window[key];
                                if (typeof obj.getView === 'function' && 
                                    typeof obj.getTargetElement === 'function') {
                                    map = obj;
                                    break;
                                }
                            }
                        } catch (e) {}
                    }
                }
                
                if (!map) {
                    return "Map not found";
                }
                
                var view = map.getView();
                if (!view) {
                    return "View not found";
                }
                
                var center = view.getCenter();
                var zoom = view.getZoom();
                var projection = view.getProjection().getCode();
                
                return JSON.stringify({
                    center: center,
                    zoom: zoom,
                    projection: projection
                });
            } catch (e) {
                console.error("Error getting map state:", e);
                return "Error: " + e.message;
            }
        })();
        """
        
        self.web_view.page().runJavaScript(script, self.handle_save_map_state)
        
    def handle_save_map_state(self, result):
        """Handle the result of retrieving the map state for saving"""
        debug_print(f"Saving map state: {result}", 0)
        
        try:
            if not result or result.startswith("Error") or result.startswith("Map not found"):
                debug_print(f"Could not save map state: {result}", 0)
                return
            
            map_state = json.loads(result)
            
            # Store in settings
            self.settings.setValue("map_center_x", map_state["center"][0])
            self.settings.setValue("map_center_y", map_state["center"][1])
            self.settings.setValue("map_zoom", map_state["zoom"])
            self.settings.setValue("map_projection", map_state["projection"])
            
            debug_print(f"Map state saved successfully. Center: {map_state['center']}, Zoom: {map_state['zoom']}", 0)
            
        except Exception as e:
            debug_print(f"Error saving map state: {str(e)}", 0)
            
    def restore_map_state(self):
        """Restore previously saved map position and zoom level"""
        # Check if we have saved map state
        if not self.settings.contains("map_center_x"):
            debug_print("No saved map state found", 0)
            return
        
        # Get saved values
        center_x = self.settings.value("map_center_x", type=float)
        center_y = self.settings.value("map_center_y", type=float)
        zoom = self.settings.value("map_zoom", type=float)
        projection = self.settings.value("map_projection", "EPSG:3857")
        
        script = f"""
        (function() {{
            try {{
                // Find the map object
                var map = null;
                if (window.map && typeof window.map.getView === 'function') {{
                    map = window.map;
                }} else {{
                    // Search for the map in global variables
                    for (var key in window) {{
                        try {{
                            if (typeof window[key] === 'object' && window[key] !== null) {{
                                var obj = window[key];
                                if (typeof obj.getView === 'function' && 
                                    typeof obj.getTargetElement === 'function') {{
                                    map = obj;
                                    break;
                                }}
                            }}
                        }} catch (e) {{}}
                    }}
                }}
                
                if (!map) {{
                    return "Map not found";
                }}
                
                var view = map.getView();
                if (!view) {{
                    return "View not found";
                }}
                
                // Check if the projection matches
                var currentProj = view.getProjection().getCode();
                if (currentProj === "{projection}") {{
                    // Same projection, set directly
                    view.setCenter([{center_x}, {center_y}]);
                    view.setZoom({zoom});
                    return "Map position and zoom restored directly";
                }} else {{
                    // Different projection, need to transform coordinates
                    if (window.ol && window.ol.proj && typeof window.ol.proj.transform === 'function') {{
                        var transformedCenter = window.ol.proj.transform(
                            [{center_x}, {center_y}],
                            "{projection}",
                            currentProj
                        );
                        view.setCenter(transformedCenter);
                        view.setZoom({zoom});
                        return "Map position and zoom restored with projection transformation";
                    }} else {{
                        // Fallback: just set the values directly
                        view.setCenter([{center_x}, {center_y}]);
                        view.setZoom({zoom});
                        return "Map position and zoom restored (without projection transformation)";
                    }}
                }}
            }} catch (e) {{
                console.error("Error restoring map state:", e);
                return "Error: " + e.message;
            }}
        }})();
        """
        
        debug_print(f"Restoring map to center: [{center_x}, {center_y}], zoom: {zoom}", 0)
        self.web_view.page().runJavaScript(script, lambda result: debug_print(f"Restore map state result: {result}", 0))

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

    def on_table_selection_changed(self):
        """Handle selection changes in the geo_table"""
        # Enable the delete and center buttons if any row is selected, disable otherwise
        has_selection = len(self.geo_table.selectedItems()) > 0
        self.delete_row_button.setEnabled(has_selection)
        self.center_selected_button.setEnabled(has_selection)
        
    def delete_selected_row(self):
        """Delete the selected row from the table and database"""
        selected_rows = sorted(set(index.row() for index in self.geo_table.selectedIndexes()))
        
        if not selected_rows:
            return
            
        # Ask for confirmation
        count = len(selected_rows)
        reply = QMessageBox.question(
            self, 'Confirm Delete', 
            f'Are you sure you want to delete {count} selected row{"s" if count > 1 else ""}?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        try:
            # Connect to the database
            if db.is_closed():
                db.connect()
            
            # Process rows in reverse order to avoid changing indices during removal
            for row in reversed(selected_rows):
                # Get the ID from the first column
                id_item = self.geo_table.item(row, 0)
                if id_item and id_item.text():
                    try:
                        record_id = int(id_item.text())
                        # Delete the record from database
                        DikeRecord.delete().where(DikeRecord.id == record_id).execute()
                        debug_print(f"Deleted database record with ID: {record_id}", 0)
                    except (ValueError, TypeError) as e:
                        debug_print(f"Error converting ID to integer: {str(e)}", 0)
                        continue
                
                # Remove row from the table
                self.geo_table.removeRow(row)
                debug_print(f"Deleted row {row} from table", 0)
            
            # Show confirmation
            self.statusBar().showMessage(f"Deleted {len(selected_rows)} row(s) from table and database", 3000)
        except Exception as e:
            debug_print(f"Error deleting rows: {str(e)}", 0)
            QMessageBox.warning(self, "Delete Error", f"Error deleting rows: {str(e)}")
        finally:
            if not db.is_closed():
                db.close()

    def center_map_on_selected(self):
        """Center the map on the selected row's coordinates and show a line marker representing the dike"""
        selected_indexes = self.geo_table.selectedIndexes()
        if not selected_indexes:
            QMessageBox.warning(self, "No Selection", "Please select a row first.")
            return
        
        # Get the row number from the first selected index
        selected_row = selected_indexes[0].row()
        
        try:
            # Get coordinates for the selected row first
            lat1_item = self.geo_table.item(selected_row, 11)  # Latitude 1
            lng1_item = self.geo_table.item(selected_row, 12)  # Longitude 1
            
            if not (lat1_item and lng1_item and lat1_item.text() and lng1_item.text()):
                QMessageBox.warning(self, "Invalid Selection", "Selected row does not have valid coordinates.")
                return
            
            selected_lat = float(lat1_item.text())
            selected_lng = float(lng1_item.text())
            
            # Collect all points from the table
            all_points = []
            for row in range(self.geo_table.rowCount()):
                try:
                    # Get distance and angle for this row
                    distance_item = self.geo_table.item(row, 7)
                    angle_item = self.geo_table.item(row, 8)
                    distance = float(distance_item.text().replace('m', '')) if distance_item and distance_item.text() else None
                    angle = float(angle_item.text().replace('°', '')) if angle_item and angle_item.text() else None
                    
                    # Get coordinates for this row
                    lat1_item = self.geo_table.item(row, 11)  # Updated column indices
                    lng1_item = self.geo_table.item(row, 12)
                    lat2_item = self.geo_table.item(row, 15)
                    lng2_item = self.geo_table.item(row, 16)
                    
                    if lat1_item and lng1_item and lat1_item.text() and lng1_item.text():
                        point = {
                            'lat1': float(lat1_item.text()),
                            'lng1': float(lng1_item.text()),
                            'lat2': float(lat2_item.text()) if lat2_item and lat2_item.text() else None,
                            'lng2': float(lng2_item.text()) if lng2_item and lng2_item.text() else None,
                            'distance': distance,
                            'angle': angle,
                            'isSelected': row == selected_row
                        }
                        all_points.append(point)
                except (ValueError, AttributeError) as e:
                    debug_print(f"Error processing row {row}: {str(e)}", 0)
                    continue

            # Create JavaScript to center the map and add markers
            center_script = f"""
            (function() {{
                try {{
                    // Find the map object
                    var map = null;
                    if (window.map && typeof window.map.getView === 'function') {{
                        map = window.map;
                    }} else {{
                        for (var key in window) {{
                            try {{
                                if (typeof window[key] === 'object' && window[key] !== null &&
                                    typeof window[key].getView === 'function') {{
                                    map = window[key];
                                    break;
                                }}
                            }} catch (e) {{}}
                        }}
                    }}
                    
                    if (!map) return "Map not found";
                    
                    // Get the view and current projection
                    var view = map.getView();
                    var currentProj = view.getProjection().getCode();
                    
                    // Remove existing marker layer
                    map.getLayers().getArray()
                        .filter(layer => layer.get('name') === 'markerLayer')
                        .forEach(layer => map.removeLayer(layer));
                    
                    // Transform coordinates function
                    var fromLonLat = function(coords) {{
                        if (window.ol && window.ol.proj && typeof window.ol.proj.transform === 'function') {{
                            return window.ol.proj.transform(coords, 'EPSG:4326', currentProj);
                        }}
                        return coords;
                    }};
                    
                    var features = [];
                    
                    // Add all points from the table
                    var points = {json.dumps(all_points)};
                    points.forEach(function(point) {{
                        // Transform coordinates to map projection
                        var center = fromLonLat([point.lng1, point.lat1]);
                        
                        // Create point feature for the start point
                        var pointFeature = new ol.Feature({{
                            geometry: new ol.geom.Point(center)
                        }});
                        
                        // Style for the point
                        var pointStyle = new ol.style.Style({{
                            image: new ol.style.Circle({{
                                radius: point.isSelected ? 6 : 4,
                                fill: new ol.style.Fill({{
                                    color: point.isSelected ? 'red' : 'blue'
                                }})
                            }})
                        }});
                        
                        pointFeature.setStyle(pointStyle);
                        features.push(pointFeature);
                        
                        // If we have distance and angle, draw a line
                        if (point.distance && point.angle) {{
                            var distance = point.distance;
                            var angle = point.angle;
                            var angleRad = (90 - angle) * Math.PI / 180;
                            
                            // Calculate the end point using the second set of coordinates if available
                            var endPoint;
                            if (point.lat2 !== null && point.lng2 !== null) {{
                                endPoint = fromLonLat([point.lng2, point.lat2]);
                            }} else {{
                                // Calculate end point using distance and angle
                                var dx = distance * Math.cos(angleRad);
                                var dy = distance * Math.sin(angleRad);
                                endPoint = [center[0] + dx, center[1] + dy];
                            }}
                            
                            // Create line feature
                            var lineFeature = new ol.Feature({{
                                geometry: new ol.geom.LineString([center, endPoint])
                            }});
                            
                            // Style for the line
                            var lineStyle = new ol.style.Style({{
                                stroke: new ol.style.Stroke({{
                                    color: point.isSelected ? 'red' : 'blue',
                                    width: point.isSelected ? 3 : 2
                                }})
                            }});
                            
                            lineFeature.setStyle(lineStyle);
                            features.push(lineFeature);
                        }}
                    }});
                    
                    // Create and add the vector layer
                    var vectorLayer = new ol.layer.Vector({{
                        source: new ol.source.Vector({{
                            features: features
                        }}),
                        name: 'markerLayer'
                    }});
                    
                    map.addLayer(vectorLayer);
                    
                    // Center on the selected point
                    var selectedPoint = points.find(p => p.isSelected);
                    if (selectedPoint) {{
                        var selectedCenter = fromLonLat([selectedPoint.lng1, selectedPoint.lat1]);
                        view.animate({{
                            center: selectedCenter,
                            zoom: 15,
                            duration: 1000
                        }});
                        
                        console.log('Centering map on:', selectedCenter);
                        return "Map centered on " + selectedCenter.join(', ');
                    }}
                    
                    return "Map updated but no selected point found";
                }} catch (e) {{
                    console.error("Error:", e);
                    return "Error: " + e.message;
                }}
            }})();
            """
            
            debug_print(f"Centering map on coordinates: {selected_lat}, {selected_lng}", 0)
            self.web_view.page().runJavaScript(center_script, self.handle_center_map_result)
            
        except Exception as e:
            debug_print(f"Error centering map: {str(e)}", 0)
            QMessageBox.warning(self, "Error", f"Failed to center map: {str(e)}")
    
    def handle_center_map_result(self, result):
        """Handle the result of the map centering operation"""
        debug_print(f"Center map result: {result}", 0)
        if result.startswith("Error") or result == "Map not found":
            QMessageBox.warning(self, "Center Map Error", result)
        else:
            self.statusBar().showMessage(result, 3000)

    def on_table_double_click(self, row, column):
        """Handle double-click on table row by centering the map on the selected coordinates"""
        debug_print(f"Double-clicked row {row}, column {column}", 0)
        self.center_map_on_selected()

    def restore_window_geometry(self):
        """Restore the window's previous size and location"""
        geometry = self.settings.value("window_geometry")
        if geometry:
            self.restoreGeometry(geometry)
            debug_print("Restored window geometry", 0)

    def import_excel_file(self):
        """Open ExcelConverterWindow for importing Excel data"""
        try:
            converter_window = ExcelConverterWindow(self)
            result = converter_window.exec_()
            if result == QDialog.Accepted:  # If dialog was accepted (not cancelled)
                # waitcursor
                QApplication.setOverrideCursor(Qt.WaitCursor)
                self.load_data_from_database()  # Refresh the main window's table
                # restore cursor
                QApplication.restoreOverrideCursor()
        except Exception as e:
            QMessageBox.critical(self, "Import Error", 
                f"Error opening Excel converter: {str(e)}")
            logging.error(f"Excel converter error: {str(e)}")


# Main function to run the application as standalone
def main():
    app = QApplication(sys.argv)
    
    # Check if WebEngine is available
    if WEB_ENGINE_AVAILABLE:
        window = KIGAMMapWindow()
        window.show()
        sys.exit(app.exec_())
    else:
        QMessageBox.critical(
            None, 
            "KIGAM Map Feature Disabled",
            "PyQt5.QtWebEngineWidgets not found. KIGAM map feature will be disabled.\n\n"
            "To enable this feature, install it with: pip install PyQtWebEngine"
        )
        sys.exit(1)


if __name__ == "__main__":
    main() 


'''
pyinstaller --name "DikeMapper_v0.0.3.exe" --onefile --noconsole DikeMapper.py
'''