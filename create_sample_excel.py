import pandas as pd
import os

# Define sample data with the required columns
data = {
    "지역": ["마전리", "마전리", "마전리", "오호", "만대리", "만대리"],
    "기호": ["ls", "ls", "ls", "Krhd", "Kad", "Kad"],
    "지층": ["연천층군 미산층", "연천층군 미산층", "연천층군 미산층", "유문암맥", "유문암, 규장암", "유문암, 규장암"],
    "대표암상": ["석회암", "석회암", "석회암", "유문암맥", "산성암맥 유문암, 규장암", "산성암맥 유문암, 규장암"],
    "시대": ["선캄브리아시대 원생누대", "선캄브리아시대 원생누대", "선캄브리아시대 원생누대", "중생대 백악기", "중생대 백악기", "중생대 백악기"],
    "각도": [-10.8, -42.3, -48.1, -2.1, -87.7, -68.9],
    "거리 (km)": [0.26, 0.18, 0.2, 0.19, 0.36, 0.39],
    "주소": [
        "경기도 연천군 미산면 아미리 576-3",
        "경기도 연천군 백학면 전동리 산 1",
        "경기도 연천군 백학면 전동리 산 71",
        "강원특별자치도 고성군 죽왕면 가진리 산 59",
        "강원특별자치도 인제군 서화면 서흥리 851-4",
        "강원특별자치도 양구군 동면 팔랑리 산 10-4"
    ],
    "색": ["하늘색", "하늘색", "하늘색", "빨간색", "빨간색", "빨간색"],
    "좌표 X": [30.62, 24.99, 20.01, 1.15, 32.11, 13.57],
    "좌표 Y": [12.49, 17, 17.56, 17.02, 19.42, 14.05],
    "사진 이름": ["0. 마전리", "0. 마전리", "0. 마전리", "1. 오호", "3. 만대리", "3. 만대리"]
}

# Create DataFrame
df = pd.DataFrame(data)

# Create data directory if it doesn't exist
data_dir = os.path.join(os.getcwd(), "data")
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

# Save to Excel file
excel_path = os.path.join(data_dir, "dike_data.xlsx")
df.to_excel(excel_path, index=False)

print(f"Sample Excel file created at: {excel_path}") 