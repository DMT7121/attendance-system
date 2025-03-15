import cv2
import numpy as np
import pickle
from googleapiclient.discovery import build
from google.oauth2 import service_account
import face_recognition
import os

# Thiết lập Google Drive và Sheets API
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']
creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds)
sheets_service = build('sheets', 'v4', credentials=creds)

# Tải dữ liệu đăng ký từ Google Sheets
def load_registered_data():
    sheet_id = '1fkbJiJYZ5Ge2EebK7qhN0uza1ATDIut76oil1WmMRjw'
    result = sheets_service.spreadsheets().values().get(spreadsheetId=sheet_id, range='DATA!A2:E').execute()
    rows = result.get('values', [])
    encodings = {}
    for row in rows:
        name, _, _, _, image_url = row
        file_id = image_url.split('id=')[1].split('&')[0]  # Lấy file ID từ URL
        file = drive_service.files().get_media(fileId=file_id).execute()
        with open(f'temp_{name}.jpg', 'wb') as f:
            f.write(file)
        image = face_recognition.load_image_file(f'temp_{name}.jpg')
        encoding = face_recognition.face_encodings(image)
        if encoding:  # Kiểm tra xem có tìm thấy khuôn mặt không
            encodings[name] = encoding[0]
        os.remove(f'temp_{name}.jpg')
    return encodings

# Nhận diện và cập nhật chấm công
def recognize_and_update():
    encodings = load_registered_data()
    sheet_id = '1fkbJiJYZ5Ge2EebK7qhN0uza1ATDIut76oil1WmMRjw'
    folder_id = '1R35hg1hHMCq409z5zWur7IOPK32MviN-'
    
    # Tải ảnh mới từ Google Drive
    results = drive_service.files().list(q=f"'{folder_id}' in parents", fields="files(id, name)").execute()
    files = results.get('files', [])
    
    for file in files:
        if 'checkin_' in file['name']:
            file_id = file['id']
            image_data = drive_service.files().get_media(fileId=file_id).execute()
            with open('temp_checkin.jpg', 'wb') as f:
                f.write(image_data)
            
            # Nhận diện khuôn mặt
            image = face_recognition.load_image_file('temp_checkin.jpg')
            face_encodings = face_recognition.face_encodings(image)
            name = 'Không xác định'
            if face_encodings:
                for known_name, known_encoding in encodings.items():
                    matches = face_recognition.compare_faces([known_encoding], face_encodings[0])
                    if matches[0]:
                        name = known_name
                        break
            
            # Cập nhật Google Sheets
            result = sheets_service.spreadsheets().values().get(spreadsheetId=sheet_id, range='CHAMCONG!A2:E').execute()
            rows = result.get('values', [])
            for i, row in enumerate(rows):
                if row[4] == f'https://drive.google.com/open?id={file_id}':
                    lat_lon = row[2].split(',')
                    distance = calculate_distance(float(lat_lon[0]), float(lat_lon[1]), 10.9760826, 106.6646541)
                    verification = 'Hợp lệ' if distance <= 30 else 'Không hợp lệ'
                    sheets_service.spreadsheets().values().update(
                        spreadsheetId=sheet_id,
                        range=f'CHAMCONG!A{i+2}:E{i+2}',
                        valueInputOption='RAW',
                        body={'values': [[name, row[1], row[2], verification, row[4]]]}
                    ).execute()
                    break
            
            os.remove('temp_checkin.jpg')
            drive_service.files().delete(fileId=file_id).execute()  # Xóa ảnh sau khi xử lý

def calculate_distance(lat1, lon1, lat2, lon2):
    from math import sin, cos, sqrt, atan2, radians
    R = 6371e3  # Bán kính Trái Đất (mét)
    φ1 = radians(lat1)
    φ2 = radians(lat2)
    Δφ = radians(lat2 - lat1)
    Δλ = radians(lon2 - lon1)
    a = sin(Δφ/2)**2 + cos(φ1) * cos(φ2) * sin(Δλ/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

if __name__ == '__main__':
    recognize_and_update()
