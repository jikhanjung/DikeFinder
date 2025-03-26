import sys
import os
import datetime
import json
import csv
import re
import math
from geopy.distance import geodesic
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                            QTableWidget, QTableWidgetItem, QMessageBox, 
                            QFileDialog, QCheckBox, QHeaderView, QSizePolicy,
                            QLayout, QSplitter)
from PyQt5.QtCore import Qt, QUrl, QObject, pyqtSignal, QTimer, QSettings
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtGui import QIcon, QFont
import pandas as pd
import numpy as np
from pyproj import Transformer
from DikeModels import GeologicalRecord, init_database, db

# Check if WebEngine is available
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    WEB_ENGINE_AVAILABLE = True
except ImportError:
    WEB_ENGINE_AVAILABLE = False

def debug_print(message, level=1):
    """Print debug messages based on debug level"""
    if KIGAMMapWindow.DEBUG_MODE >= level:
        print(f"[DEBUG] {message}")

class KIGAMMapWindow(QMainWindow):
    """A window to display the geological map from KIGAM website"""
    DEBUG_MODE = 0  # Default: no debugging (0), Basic (1), Verbose (2)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self.init_database()
        self.load_data_from_database()
        
    def initUI(self):
        # ... existing UI initialization code ...
        self.setWindowTitle("DikeMapper v0.0.2 - KIGAM Geological Map")
        self.setGeometry(200, 200, 1000, 800)
        
        # Initialize database
        self.init_database()
        
        # Create central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        # Settings for credential storage
        self.settings = QSettings("PaleoBytes", "DikeMapper")
        
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
        
        self.export_table_button = QPushButton("Export Table")
        self.export_table_button.setToolTip("Export the table data to a CSV file")
        self.export_table_button.clicked.connect(self.export_geo_table)

        self.import_excel_button = QPushButton("Import Excel")
        self.import_excel_button.setToolTip("Import data from Excel")
        #self.import_excel_button.clicked.connect(self.import_excel_file)

        table_controls_layout.addWidget(self.add_to_table_button)
        table_controls_layout.addWidget(self.delete_row_button)
        table_controls_layout.addWidget(self.center_selected_button)
        table_controls_layout.addWidget(self.clear_table_button)
        table_controls_layout.addWidget(self.export_table_button)
        table_controls_layout.addWidget(self.import_excel_button)
        
        self.table_layout.addLayout(table_controls_layout)
        
        # Create the actual table for geological data
        self.geo_table = QTableWidget()
        self.geo_table.setColumnCount(8)  # Increased from 6 to 8 for distance and angle
        self.geo_table.setHorizontalHeaderLabels(["기호 (Symbol)", "지층 (Stratum)", 
                                                "대표암상 (Rock Type)", "시대 (Era)", 
                                                "도폭 (Map Sheet)", "주소 (Address)",
                                                "거리 (Distance)", "각도 (Angle)"])
        self.geo_table.horizontalHeader().setStretchLastSection(True)
        self.geo_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Enable vertical scrollbar
        self.geo_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.geo_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Connect selection changed signal to enable/disable delete button
        self.geo_table.itemSelectionChanged.connect(self.on_table_selection_changed)
        
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
        init_database()
        
    def load_data_from_database(self):
        """Load data from the database into the table"""
        try:
            # Clear existing table data
            self.geo_table.setRowCount(0)
            
            # Ensure we have enough columns for all data
            if self.geo_table.columnCount() < 16:
                self.geo_table.setColumnCount(16)
                headers = ["기호 (Symbol)", "지층 (Stratum)", 
                           "대표암상 (Rock Type)", "시대 (Era)", 
                           "도폭 (Map Sheet)", "주소 (Address)",
                           "거리 (Distance)", "각도 (Angle)",
                           "X 좌표 1", "Y 좌표 1", "위도 (Latitude) 1", "경도 (Longitude) 1",
                           "X 좌표 2", "Y 좌표 2", "위도 (Latitude) 2", "경도 (Longitude) 2"]
                self.geo_table.setHorizontalHeaderLabels(headers)
            
            # Load records from database
            records = GeologicalRecord.select().order_by(GeologicalRecord.created_date)
            
            for record in records:
                row = self.geo_table.rowCount()
                self.geo_table.insertRow(row)
                
                # Add basic information to table
                self.geo_table.setItem(row, 0, QTableWidgetItem(record.symbol or ""))
                self.geo_table.setItem(row, 1, QTableWidgetItem(record.stratum or ""))
                self.geo_table.setItem(row, 2, QTableWidgetItem(record.rock_type or ""))
                self.geo_table.setItem(row, 3, QTableWidgetItem(record.era or ""))
                self.geo_table.setItem(row, 4, QTableWidgetItem(record.map_sheet or ""))
                self.geo_table.setItem(row, 5, QTableWidgetItem(record.address or ""))
                
                # Add distance and angle if available
                if record.distance is not None:
                    self.geo_table.setItem(row, 6, QTableWidgetItem(f"{record.distance:.1f}m"))
                if record.angle is not None:
                    self.geo_table.setItem(row, 7, QTableWidgetItem(f"{record.angle:.1f}°"))
                
                # Add first set of coordinates (X1, Y1, Lat1, Lng1)
                if record.x_coord_1 is not None:
                    self.geo_table.setItem(row, 8, QTableWidgetItem(f"{record.x_coord_1:.3f}"))
                if record.y_coord_1 is not None:
                    self.geo_table.setItem(row, 9, QTableWidgetItem(f"{record.y_coord_1:.3f}"))
                if record.lat_1 is not None:
                    self.geo_table.setItem(row, 10, QTableWidgetItem(f"{record.lat_1:.6f}"))
                if record.lng_1 is not None:
                    self.geo_table.setItem(row, 11, QTableWidgetItem(f"{record.lng_1:.6f}"))
                
                # Add second set of coordinates (X2, Y2, Lat2, Lng2)
                if record.x_coord_2 is not None:
                    self.geo_table.setItem(row, 12, QTableWidgetItem(f"{record.x_coord_2:.3f}"))
                if record.y_coord_2 is not None:
                    self.geo_table.setItem(row, 13, QTableWidgetItem(f"{record.y_coord_2:.3f}"))
                if record.lat_2 is not None:
                    self.geo_table.setItem(row, 14, QTableWidgetItem(f"{record.lat_2:.6f}"))
                if record.lng_2 is not None:
                    self.geo_table.setItem(row, 15, QTableWidgetItem(f"{record.lng_2:.6f}"))
            
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
        
        if info_dict:
            # First, ensure we have enough columns
            if self.geo_table.columnCount() < 16:  # We need 16 columns for all the data
                self.geo_table.setColumnCount(16)
                headers = ["기호 (Symbol)", "지층 (Stratum)", 
                           "대표암상 (Rock Type)", "시대 (Era)", 
                           "도폭 (Map Sheet)", "주소 (Address)",
                           "거리 (Distance)", "각도 (Angle)",
                           "X 좌표 1", "Y 좌표 1", "위도 (Latitude) 1", "경도 (Longitude) 1",
                           "X 좌표 2", "Y 좌표 2", "위도 (Latitude) 2", "경도 (Longitude) 2"]
                self.geo_table.setHorizontalHeaderLabels(headers)
            
            # Add a new row to the table
            row_position = self.geo_table.rowCount()
            self.geo_table.insertRow(row_position)
            
            # Debug print current values
            debug_print(f"Adding to table - Row position: {row_position}", 0)
            debug_print(f"Symbol: {info_dict.get('symbol', '')}", 0)
            debug_print(f"Distance: {self.current_distance_measurement}", 0)
            debug_print(f"Angle: {self.current_angle_measurement}", 0)
            debug_print(f"Previous coords: {self.previous_raw_x}, {self.previous_raw_y}, {self.previous_lat}, {self.previous_lng}", 0)
            debug_print(f"Current coords: {self.current_raw_x}, {self.current_raw_y}, {self.current_lat}, {self.current_lng}", 0)
            
            # Add the extracted information to the cells
            self.geo_table.setItem(row_position, 0, QTableWidgetItem(info_dict.get('symbol', '')))
            self.geo_table.setItem(row_position, 1, QTableWidgetItem(info_dict.get('stratum', '')))
            self.geo_table.setItem(row_position, 2, QTableWidgetItem(info_dict.get('rock_type', '')))
            self.geo_table.setItem(row_position, 3, QTableWidgetItem(info_dict.get('era', '')))
            self.geo_table.setItem(row_position, 4, QTableWidgetItem(info_dict.get('map_sheet', '')))
            self.geo_table.setItem(row_position, 5, QTableWidgetItem(info_dict.get('address', '')))
            
            # Extract numeric values for database storage
            distance_value = None
            angle_value = None
            
            # Add distance and angle if available
            if hasattr(self, 'current_distance_measurement') and self.current_distance_measurement is not None:
                debug_print(f"Processing distance measurement: {self.current_distance_measurement}", 0)
                self.geo_table.setItem(row_position, 6, QTableWidgetItem(f"{self.current_distance_measurement}m"))
                debug_print(f"Added distance to table: {self.current_distance_measurement}m", 0)
                
                # Convert to float for database
                try:
                    distance_value = float(self.current_distance_measurement)
                except (ValueError, TypeError):
                    distance_value = None
                
                if hasattr(self, 'current_angle_measurement') and self.current_angle_measurement is not None:
                    self.geo_table.setItem(row_position, 7, QTableWidgetItem(f"{self.current_angle_measurement}°"))
                    debug_print(f"Added angle to table: {self.current_angle_measurement}°", 0)
                    
                    # Convert to float for database
                    try:
                        angle_value = float(self.current_angle_measurement)
                    except (ValueError, TypeError):
                        angle_value = None
            else:
                debug_print("No distance measurement available", 0)
            
            # Add previous coordinates (X1, Y1, Lat1, Lng1) - starting at column 8
            prev_x, prev_y, prev_lat, prev_lng = None, None, None, None
            # trim the previous_raw_x and previous_raw_y to 3 decimal places
            self.previous_raw_x = round(self.previous_raw_x, 3)
            self.previous_raw_y = round(self.previous_raw_y, 3)
            self.current_raw_x = round(self.current_raw_x, 3)
            self.current_raw_y = round(self.current_raw_y, 3)
            self.previous_lat = round(self.previous_lat, 6)
            self.previous_lng = round(self.previous_lng, 6)
            self.current_lat = round(self.current_lat, 6)
            self.current_lng = round(self.current_lng, 6)
            
            if hasattr(self, 'previous_raw_x') and self.previous_raw_x is not None:
                self.geo_table.setItem(row_position, 8, QTableWidgetItem(str(self.previous_raw_x)))
                debug_print(f"Added previous X: {self.previous_raw_x}", 0)
                prev_x = float(self.previous_raw_x)
            
            if hasattr(self, 'previous_raw_y') and self.previous_raw_y is not None:
                self.geo_table.setItem(row_position, 9, QTableWidgetItem(str(self.previous_raw_y)))
                debug_print(f"Added previous Y: {self.previous_raw_y}", 0)
                prev_y = float(self.previous_raw_y)
            
            if hasattr(self, 'previous_lat') and self.previous_lat is not None:
                self.geo_table.setItem(row_position, 10, QTableWidgetItem(str(self.previous_lat)))
                debug_print(f"Added previous Lat: {self.previous_lat}", 0)
                prev_lat = float(self.previous_lat)
            
            if hasattr(self, 'previous_lng') and self.previous_lng is not None:
                self.geo_table.setItem(row_position, 11, QTableWidgetItem(str(self.previous_lng)))
                debug_print(f"Added previous Lng: {self.previous_lng}", 0)
                prev_lng = float(self.previous_lng)
            
            # Add current coordinates (X2, Y2, Lat2, Lng2) - starting at column 12
            curr_x, curr_y, curr_lat, curr_lng = None, None, None, None
            
            if hasattr(self, 'current_raw_x') and self.current_raw_x is not None:
                self.geo_table.setItem(row_position, 12, QTableWidgetItem(str(self.current_raw_x)))
                debug_print(f"Added current X: {self.current_raw_x}", 0)
                curr_x = float(self.current_raw_x)
            
            if hasattr(self, 'current_raw_y') and self.current_raw_y is not None:
                self.geo_table.setItem(row_position, 13, QTableWidgetItem(str(self.current_raw_y)))
                debug_print(f"Added current Y: {self.current_raw_y}", 0)
                curr_y = float(self.current_raw_y)
            
            if hasattr(self, 'current_lat') and self.current_lat is not None:
                self.geo_table.setItem(row_position, 14, QTableWidgetItem(str(self.current_lat)))
                debug_print(f"Added current Lat: {self.current_lat}", 0)
                curr_lat = float(self.current_lat)
            
            if hasattr(self, 'current_lng') and self.current_lng is not None:
                self.geo_table.setItem(row_position, 15, QTableWidgetItem(str(self.current_lng)))
                debug_print(f"Added current Lng: {self.current_lng}", 0)
                curr_lng = float(self.current_lng)
            
            # Save to database
            try:
                db.connect()
                record = GeologicalRecord.create(
                    symbol=info_dict.get('symbol', ''),
                    stratum=info_dict.get('stratum', ''),
                    rock_type=info_dict.get('rock_type', ''),
                    era=info_dict.get('era', ''),
                    map_sheet=info_dict.get('map_sheet', ''),
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
                debug_print(f"Saved record to database with ID: {record.id}", 0)
            except Exception as e:
                debug_print(f"Error saving to database: {str(e)}", 0)
                QMessageBox.warning(self, "Database Error", f"Error saving to database: {str(e)}")
            finally:
                if not db.is_closed():
                    db.close()
            
            # Select the new row
            self.geo_table.selectRow(row_position)
            debug_print(f"Selected row {row_position}", 0)
            
            # Show confirmation
            self.statusBar().showMessage(f"Added geological information to row {row_position + 1}", 3000)
            
            # Reset tool states
            if self.info_button.isChecked():
                self.info_button.setChecked(False)
                self.info_tool_active = False
                self.geo_info_label.setText("")
                self.geo_info_label.setStyleSheet("background-color: rgba(255, 255, 255, 220); padding: 2px; border-radius: 3px;")
            
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
                            //distanceButton.classList.remove('active');
                            distanceButton.click();
                            console.log('Deactivated map distance button');
                        }
                    })();
                    """,
                    lambda result: debug_print("Map distance button deactivated", 0)
                )
            
            # Reset current info and measurements
            self.current_lat = ModuleNotFoundError
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
            self.update_coordinates()
            self.add_to_table_button.setEnabled(False)
            
        else:
            QMessageBox.warning(self, "Parsing Error", "Could not parse the geological information")
    
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
                    db.connect()
                    GeologicalRecord.delete().execute()
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
        """Override closeEvent to save map position and zoom level"""
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
            db.connect()
            
            # Get the database records to delete
            records = GeologicalRecord.select()
            
            # Process rows in reverse order to avoid changing indices during removal
            for row in reversed(selected_rows):
                # Get the ID from the database (we'll need to identify this row in the database)
                # We'll use symbol, stratum, rock_type, and coords to find matching records
                symbol = self.geo_table.item(row, 0).text() if self.geo_table.item(row, 0) else ""
                rock_type = self.geo_table.item(row, 2).text() if self.geo_table.item(row, 2) else ""
                
                # Get coordinate values for matching
                x1 = self.geo_table.item(row, 8).text() if row < self.geo_table.rowCount() and self.geo_table.columnCount() > 8 and self.geo_table.item(row, 8) else None
                y1 = self.geo_table.item(row, 9).text() if row < self.geo_table.rowCount() and self.geo_table.columnCount() > 9 and self.geo_table.item(row, 9) else None
                
                # Try to find and delete matching records from the database
                query = records
                if symbol:
                    query = query.where(GeologicalRecord.symbol == symbol)
                if rock_type:
                    query = query.where(GeologicalRecord.rock_type == rock_type)
                if x1 and y1:
                    try:
                        x1_val = float(x1)
                        y1_val = float(y1)
                        query = query.where(GeologicalRecord.x_coord_1 == x1_val, GeologicalRecord.y_coord_1 == y1_val)
                    except (ValueError, TypeError):
                        pass
                        
                # Delete matching records
                count = query.count()
                if count > 0:
                    for record in query:
                        record.delete_instance()
                    debug_print(f"Deleted {count} database record(s) matching row {row}", 0)
                
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
        """Center the map on the selected row's coordinates"""
        selected_indexes = self.geo_table.selectedIndexes()
        if not selected_indexes:
            QMessageBox.warning(self, "No Selection", "Please select a row first.")
            return
        
        # Get the row number from the first selected index
        selected_row = selected_indexes[0].row()
        
        # Get the coordinates from the row (checking both sets of coordinates)
        lat1 = None
        lng1 = None
        x1 = None
        y1 = None
        
        try:
            # Try lat/lng coordinates first (WGS84) - columns 10 and 11
            if (self.geo_table.columnCount() > 11 and 
                self.geo_table.item(selected_row, 10) and 
                self.geo_table.item(selected_row, 11)):
                lat1_item = self.geo_table.item(selected_row, 10)
                lng1_item = self.geo_table.item(selected_row, 11)
                
                if lat1_item and lng1_item and lat1_item.text() and lng1_item.text():
                    lat1 = float(lat1_item.text())
                    lng1 = float(lng1_item.text())
                    debug_print(f"Found WGS84 coordinates: Lat={lat1}, Lng={lng1}", 0)
            
            # If WGS84 coordinates aren't available, try raw coordinates - columns 8 and 9
            if lat1 is None or lng1 is None:
                if (self.geo_table.columnCount() > 9 and 
                    self.geo_table.item(selected_row, 8) and 
                    self.geo_table.item(selected_row, 9)):
                    x1_item = self.geo_table.item(selected_row, 8)
                    y1_item = self.geo_table.item(selected_row, 9)
                    
                    if x1_item and y1_item and x1_item.text() and y1_item.text():
                        x1 = float(x1_item.text())
                        y1 = float(y1_item.text())
                        debug_print(f"Found raw coordinates: X={x1}, Y={y1}", 0)
            
            # If we don't have any coordinates, display error
            if (lat1 is None or lng1 is None) and (x1 is None or y1 is None):
                QMessageBox.warning(self, "No Coordinates", "Selected row doesn't have valid coordinates.")
                return
            
            # Create JavaScript to center the map using the available coordinates
            if lat1 is not None and lng1 is not None:
                # Using WGS84 coordinates
                center_script = f"""
                (function() {{
                    try {{
                        // Find the map object
                        var map = null;
                        if (window.map && typeof window.map.getView === 'function') {{
                            map = window.map;
                        }} else {{
                            // Look for the map in global variables
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
                        
                        // Transform WGS84 coordinates to map projection
                        var fromLonLat = ol.proj.fromLonLat || ol.proj.transform;
                        if (typeof fromLonLat === 'function') {{
                            var center = fromLonLat([{lng1}, {lat1}], map.getView().getProjection().getCode());
                            map.getView().setCenter(center);
                            map.getView().setZoom(15);  // Adjust zoom level as needed
                            return "Map centered on WGS84 coordinates";
                        }} else {{
                            return "Transformation function not found";
                        }}
                    }} catch (e) {{
                        console.error("Error centering map:", e);
                        return "Error: " + e.message;
                    }}
                }})();
                """
            else:
                # Using raw coordinates
                center_script = f"""
                (function() {{
                    try {{
                        // Find the map object
                        var map = null;
                        if (window.map && typeof window.map.getView === 'function') {{
                            map = window.map;
                        }} else {{
                            // Look for the map in global variables
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
                        
                        map.getView().setCenter([{x1}, {y1}]);
                        map.getView().setZoom(15);  // Adjust zoom level as needed
                        return "Map centered on raw coordinates";
                    }} catch (e) {{
                        console.error("Error centering map:", e);
                        return "Error: " + e.message;
                    }}
                }})();
                """
            
            # Execute the script and handle the result
            self.web_view.page().runJavaScript(center_script, self.handle_center_map_result)
            
        except Exception as e:
            debug_print(f"Error centering map: {str(e)}", 0)
            QMessageBox.warning(self, "Error", f"Failed to center map: {str(e)}")
    
    def handle_center_map_result(self, result):
        """Handle the result of the map centering operation"""
        debug_print(f"Center map result: {result}", 0)
        if result.startswith("Error") or result == "Map not found" or result == "Transformation function not found":
            QMessageBox.warning(self, "Center Map Error", result)
        else:
            self.statusBar().showMessage(f"Map centered on selected coordinates", 3000)

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
pyinstaller --name "DikeMapper_v0.0.1.exe" --onefile --noconsole DikeMapper.py
'''