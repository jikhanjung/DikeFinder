import pandas as pd
import os
import sys

# Set console output encoding to UTF-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Path to the Excel file
data_dir = os.path.join(os.getcwd(), "data")
target_file = "석영맥(통합)v1.xlsx"
excel_path = os.path.join(data_dir, target_file)

print(f"Examining Excel file: {excel_path}")
print(f"File exists: {os.path.exists(excel_path)}")

try:
    # Read the Excel file
    df = pd.read_excel(excel_path)
    
    # Print basic information
    print(f"\nDataFrame shape: {df.shape}")
    print(f"Number of rows: {len(df)}")
    print(f"Number of columns: {len(df.columns)}")
    
    # Print column names
    print("\nColumns:")
    for i, col in enumerate(df.columns):
        print(f"  {i}: {col}")
    
    # Print first few rows
    print("\nFirst 3 rows:")
    print(df.head(3).to_string())
    
    # Check for expected columns
    expected_columns = ["지역", "기호", "지층", "대표암상", "시대", "각도", 
                        "거리 (km)", "주소", "색", "좌표 X", "좌표 Y", "사진 이름"]
    
    print("\nChecking for expected columns:")
    for col in expected_columns:
        if col in df.columns:
            print(f"  ✓ Found: {col}")
        else:
            print(f"  ✗ Missing: {col}")
    
    # Try to find possible equivalent columns if exact matches aren't found
    if any(col not in df.columns for col in expected_columns):
        print("\nPossible equivalent columns:")
        for expected in expected_columns:
            if expected not in df.columns:
                for actual in df.columns:
                    if expected in actual or actual in expected:
                        print(f"  {expected} might match with {actual}")
    
except Exception as e:
    print(f"Error reading Excel file: {e}")
    import traceback
    traceback.print_exc() 