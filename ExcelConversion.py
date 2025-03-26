
        def import_excel_file(self):
            """Import data from an Excel file"""
            file_name, _ = QFileDialog.getOpenFileName(
                self, "Import Geological Data", "", "Excel Files (*.xlsx);;All Files (*)"
            )
            
            if not file_name:
                return  # User canceled
            
            try:
                # Read the Excel file
                df = pd.read_excel(file_name)
                column_header_text = "지역	기호	지층	대표암상	시대	각도	거리 (km)	주소	색	좌표 X	좌표 Y	사진 이름	코드1 좌표 Lat	코드 1 좌표 Lng"
                column_header_list = column_header_text.split('\t')
                
                # Define column names
                image_col = '사진 이름'
                x_col = '좌표 X'
                y_col = '좌표 Y'
                lat_col = '코드1 좌표 Lat'
                lng_col = '코드 1 좌표 Lng'
                
                # Add new columns for calculated coordinates
                df['X_3857'] = np.nan
                df['Y_3857'] = np.nan
                df['Calculated_Lat'] = np.nan
                df['Calculated_Lng'] = np.nan
                df['Pixel_X'] = np.nan
                df['Pixel_Y'] = np.nan
                df['Pixel_Y_Flipped'] = np.nan
                
                # Create a transformer from WGS84 (EPSG:4326) to Web Mercator (EPSG:3857)
                transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
                transformer_back = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
                
                # Convert coordinate columns to float, replacing any non-numeric values with NaN
                for col in [x_col, y_col, lat_col, lng_col]:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # Constants for coordinate conversion
                CM_TO_INCH = 0.393701  # 1 cm = 0.393701 inches
                DPI = 96  # dots per inch
                
                # Process each image group
                image_groups = df.groupby(image_col)
                
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
                                df.at[row.name, 'Pixel_X'] = x_val
                                df.at[row.name, 'Pixel_Y'] = y_val
                                
                                # Invert y coordinate
                                y_val_flipped = max_y - y_val
                                df.at[row.name, 'Pixel_Y_Flipped'] = y_val_flipped
                                
                                # Transform lat/lng to EPSG:3857
                                x_3857, y_3857 = transformer.transform(row[lng_col], row[lat_col])
                                df.at[row.name, 'X_3857'] = x_3857
                                df.at[row.name, 'Y_3857'] = y_3857
                                
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
                
                for idx, row in df.iterrows():
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
                            if pd.isna(df.at[idx, 'Pixel_X']):
                                df.at[idx, 'Pixel_X'] = x_val
                                df.at[idx, 'Pixel_Y'] = y_val
                            
                            # Invert y coordinate
                            y_val_flipped = transform['max_y'] - y_val
                            if pd.isna(df.at[idx, 'Pixel_Y_Flipped']):
                                df.at[idx, 'Pixel_Y_Flipped'] = y_val_flipped
                            
                            # Calculate EPSG:3857 coordinates
                            x_3857 = transform['x_slope'] * x_val + transform['x_intercept']
                            y_3857 = transform['y_slope'] * y_val_flipped + transform['y_intercept']
                            
                            # Store EPSG:3857 coordinates if not already stored
                            if pd.isna(df.at[idx, 'X_3857']):
                                df.at[idx, 'X_3857'] = x_3857
                                df.at[idx, 'Y_3857'] = y_3857
                            
                            # Calculate and store WGS84 coordinates if not already present
                            if pd.isna(row[lat_col]) or pd.isna(row[lng_col]):
                                lng, lat = transformer_back.transform(x_3857, y_3857)
                                df.at[idx, 'Calculated_Lat'] = lat
                                df.at[idx, 'Calculated_Lng'] = lng
                            
                    except Exception as e:
                        print(f"Error processing row {idx}: {str(e)}")
                        continue
                
                # Save the results to a new Excel file
                output_file = os.path.splitext(file_name)[0] + '_with_coordinates.xlsx'
                print(f"\nSaving results to {output_file}")
                df.to_excel(output_file, index=False)
                print("Save completed.")
                
                QMessageBox.information(self, "Import Complete", 
                    f"Coordinates have been calculated and saved to:\n{output_file}")

            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Error importing data: {str(e)}")
                
