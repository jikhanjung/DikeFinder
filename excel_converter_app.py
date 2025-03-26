import sys
import os
import pandas as pd
import numpy as np
from pyproj import Transformer
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                            QHBoxLayout, QWidget, QTableWidget, QTableWidgetItem, 
                            QFileDialog, QMessageBox, QHeaderView)
from DikeModels import GeologicalRecord, init_database

class ExcelConverterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.df = None
        self.initUI()
        init_database()  # Initialize the database
        
    def initUI(self):
        self.setWindowTitle('Excel Coordinate Converter')
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create button layout
        button_layout = QHBoxLayout()
        
        # Create Load, Save, and Save to DB buttons
        self.load_button = QPushButton('Load Excel File', self)
        self.load_button.clicked.connect(self.load_excel_file)
        self.save_button = QPushButton('Save Excel File', self)
        self.save_button.clicked.connect(self.save_excel_file)
        self.save_button.setEnabled(False)
        self.save_db_button = QPushButton('Save to Database', self)
        self.save_db_button.clicked.connect(self.save_to_database)
        self.save_db_button.setEnabled(False)
        
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.save_db_button)
        layout.addLayout(button_layout)
        
        # Create table widget
        self.table = QTableWidget(self)
        layout.addWidget(self.table)
        
        self.show()
    
    def update_table(self):
        if self.df is None:
            return
            
        # Set table dimensions
        self.table.setRowCount(len(self.df))
        self.table.setColumnCount(len(self.df.columns))
        
        # Set headers
        self.table.setHorizontalHeaderLabels(self.df.columns)
        
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
                self.table.setItem(i, j, item)
        
        # Adjust column widths
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        
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
                '도폭': 'map_sheet',
                '주소': 'address',
                '거리 (km)': 'distance',
                '각도': 'angle',
                'X_3857': 'x_coord_1',
                'Y_3857': 'y_coord_1',
                'Calculated_Lat': 'lat_1',
                'Calculated_Lng': 'lng_1'
            }
            
            # Convert distance from km to meters
            if '거리 (km)' in self.df.columns:
                self.df['거리 (km)'] = self.df['거리 (km)'] * 1000
            
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
                
                records.append(GeologicalRecord(**record_data))
            
            # Bulk insert records
            GeologicalRecord.bulk_create(records)
            
            QMessageBox.information(self, "Database Save Complete", 
                f"Successfully saved {len(records)} records to the database.")
                
        except Exception as e:
            QMessageBox.critical(self, "Database Save Error", 
                f"Error saving to database: {str(e)}")
    
    def load_excel_file(self):
        """Import data from an Excel file"""
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Import Geological Data", "", "Excel Files (*.xlsx);;All Files (*)"
        )
        
        if not file_name:
            return  # User canceled
        
        try:
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
            self.save_button.setEnabled(True)
            self.save_db_button.setEnabled(True)  # Enable database save button
            
            QMessageBox.information(self, "Import Complete", 
                "Data has been loaded and coordinates calculated successfully.")

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Error importing data: {str(e)}")
    
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

def main():
    app = QApplication(sys.argv)
    ex = ExcelConverterApp()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main() 