from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                           QLabel, QProgressBar, QTextEdit, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from DikeModels import DikeRecord, SyncEvent, SyncEventRecord, db
import requests
import json
import datetime
from PyQt5.QtCore import QSettings

class SyncWorker(QThread):
    """Worker thread to handle sync operations"""
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, base_url, records):
        super().__init__()
        self.base_url = base_url
        self.records = records
        self.sync_event = None
        
    def run(self):
        try:
            with db.atomic() as transaction:
                try:
                    # Step 1: Create new sync event on server
                    self.progress.emit("\nRequesting new sync event from server...")
                    response = requests.post(f"{self.base_url}/sync-events/create_new/")
                    
                    if response.status_code != 200:
                        raise Exception(f"Failed to create sync event: {response.text}")
                    
                    event_data = response.json()
                    event_id = event_data['event_id']
                    self.progress.emit(f"Received event_id: {event_id}")
                    
                    # Step 2: Create local sync event record
                    self.sync_event = SyncEvent.create(
                        event_id=event_id,
                        status='in_progress',
                        timestamp=datetime.datetime.now()
                    )
                    
                    # Step 3: Submit all records
                    total_records = len(self.records)
                    success_count = 0
                    fail_count = 0
                    
                    self.progress.emit(f"\nStarting sync of {total_records} records...")
                    
                    for i, record in enumerate(self.records, 1):
                        try:
                            record_data = {
                                "event_id": event_id,
                                "dike_record": {
                                    "symbol": record.symbol,
                                    "stratum": record.stratum,
                                    "rock_type": record.rock_type,
                                    "era": record.era,
                                    "map_sheet": record.map_sheet,
                                    "address": record.address,
                                    "distance": float(record.distance) if record.distance else None,
                                    "angle": float(record.angle) if record.angle else None,
                                    "x_coord_1": float(record.x_coord_1) if record.x_coord_1 else None,
                                    "y_coord_1": float(record.y_coord_1) if record.y_coord_1 else None,
                                    "lat_1": float(record.lat_1) if record.lat_1 else None,
                                    "lng_1": float(record.lng_1) if record.lng_1 else None,
                                    "x_coord_2": float(record.x_coord_2) if record.x_coord_2 else None,
                                    "y_coord_2": float(record.y_coord_2) if record.y_coord_2 else None,
                                    "lat_2": float(record.lat_2) if record.lat_2 else None,
                                    "lng_2": float(record.lng_2) if record.lng_2 else None,
                                    "memo": record.memo,
                                    "modified_date": record.modified_date.isoformat() if record.modified_date else None
                                }
                            }
                            
                            # Only show progress every 10 records or on failure
                            if i % 10 == 0:
                                self.progress.emit(f"Syncing record {i}/{total_records}: {record.symbol}")
                            
                            response = requests.post(
                                f"{self.base_url}/submit-dike-record/",
                                json=record_data
                            )
                            
                            sync_result = 'success' if response.status_code == 201 else 'failed'
                            result_message = ('Successfully synced' if response.status_code == 201 
                                            else f"Failed: {response.text}")
                            
                            SyncEventRecord.create(
                                sync_event=self.sync_event,
                                dike_record=record,
                                sync_result=sync_result,
                                result_message=result_message,
                                timestamp=datetime.datetime.now()
                            )
                            
                            if sync_result == 'success':
                                success_count += 1
                            else:
                                fail_count += 1
                                self.progress.emit(f"Failed to sync record {i}/{total_records} ({record.symbol}): {response.text}")
                            
                        except Exception as e:
                            fail_count += 1
                            self.progress.emit(f"Error syncing record {i}/{total_records} ({record.symbol}): {str(e)}")
                            SyncEventRecord.create(
                                sync_event=self.sync_event,
                                dike_record=record,
                                sync_result='failed',
                                result_message=str(e),
                                timestamp=datetime.datetime.now()
                            )
                    
                    # Step 4: Update final sync status
                    final_status = 'completed' if fail_count == 0 else 'completed_with_errors'
                    self.sync_event.status = final_status
                    self.sync_event.error_message = (f"{fail_count} records failed to sync" 
                                                   if fail_count > 0 else None)
                    self.sync_event.save()
                    
                    # Show summary
                    self.progress.emit("\nSync completed!")
                    self.progress.emit(f"Total records: {total_records}")
                    self.progress.emit(f"Successfully synced: {success_count}")
                    self.progress.emit(f"Failed: {fail_count}")
                    
                    self.finished.emit(True)
                    
                except Exception as e:
                    if self.sync_event:
                        self.sync_event.status = 'failed'
                        self.sync_event.error_message = str(e)
                        self.sync_event.save()
                    transaction.rollback()
                    raise
                    
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False)

class SyncDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.settings = QSettings('KIGAM', 'DikeMapper')
        self.base_url = self.settings.value('sync/server_url', 
                                          "http://127.0.0.1:8000/dikesync")
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("Sync Data")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Status label
        self.status_label = QLabel("Ready to sync")
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.sync_button = QPushButton("Start Sync")
        self.sync_button.clicked.connect(self.start_sync)
        button_layout.addWidget(self.sync_button)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def log_message(self, message):
        self.log_text.append(message)
        
    def start_sync(self):
        # Get records from parent window
        records = self.parent.get_records_to_sync()
        if not records:
            QMessageBox.warning(self, "No Data", 
                              "No records found to sync.")
            return
        
        # Confirm sync
        reply = QMessageBox.question(
            self, "Confirm Sync",
            f"Ready to sync {len(records)} records. Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
            
        # Update UI
        self.sync_button.setEnabled(False)
        self.progress_bar.show()
        self.status_label.setText("Syncing...")
        
        # Create and start worker thread
        self.worker = SyncWorker(self.base_url, records)
        self.worker.progress.connect(self.log_message)
        self.worker.error.connect(self.handle_error)
        self.worker.finished.connect(self.handle_sync_complete)
        self.worker.start()
        
    def handle_error(self, error_message):
        self.log_message(f"Error: {error_message}")
        self.status_label.setText("Sync failed")
        self.progress_bar.hide()
        self.sync_button.setEnabled(True)
        
        QMessageBox.critical(self, "Sync Error", 
                           f"An error occurred during sync:\n{error_message}")
        
    def handle_sync_complete(self, success):
        self.progress_bar.hide()
        if success:
            self.status_label.setText("Sync completed successfully")
            QMessageBox.information(self, "Success", 
                                  "Data synchronization completed successfully!")
        self.sync_button.setEnabled(True) 