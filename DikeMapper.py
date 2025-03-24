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
    if KIGAMMapWindow.DEBUG_MODE >= level:
        print(message)

# Set default debug level
DEBUG_MODE = 1  # Default: 0 = off, 1 = basic, 2 = verbose


# Define the KIGAMMapWindow class only if WebEngine is available
if WEB_ENGINE_AVAILABLE:
    class KIGAMMapWindow(QMainWindow):
        """A window to display the geological map from KIGAM website"""
        DEBUG_MODE = 0  # Default: no debugging (0), Basic (1), Verbose (2)
        
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

else:
    class KIGAMMapWindow:
        """Placeholder class for KIGAMMapWindow"""
        pass 

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