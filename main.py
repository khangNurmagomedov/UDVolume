import cv2
import numpy as np
import mediapipe as mp
import math
import os
import urllib.request
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

# -------------------------------------------------------------
# 1. Khởi tạo PyCAW để điều khiển âm lượng Windows
# -------------------------------------------------------------
try:
    device = AudioUtilities.GetSpeakers()
    volume = device.EndpointVolume
    volRange = volume.GetVolumeRange()  # Ví dụ: (-65.5, 0.0, 0.5)
    minVol = volRange[0]
    maxVol = volRange[1]
except Exception as e:
    print(f"Loi khi khoi tao PyCAW audio: {e}")
    minVol, maxVol = -65.0, 0.0

# -------------------------------------------------------------
# 2. Khởi tạo MediaPipe Hands & Webcam
# -------------------------------------------------------------
# Kiểm tra phiên bản MediaPipe (hỗ trợ cả MediaPipe 1.0+ Tasks API và phiên bản Solutions cũ)
use_tasks_api = not hasattr(mp, 'solutions')

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),        # Ngón cái
    (0, 5), (5, 6), (6, 7), (7, 8),        # Ngón trỏ
    (5, 9), (9, 10), (10, 11), (11, 12),   # Ngón giữa
    (9, 13), (13, 14), (14, 15), (15, 16), # Ngón áp út
    (13, 17), (17, 18), (18, 19), (19, 20),# Ngón út
    (0, 5), (5, 9), (9, 13), (13, 17), (0, 17) # Lòng bàn tay
]

if use_tasks_api:
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision

    MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")
    MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"

    if not os.path.exists(MODEL_PATH):
        print("Dang tai mo hinh hand_landmarker.task...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("Tai mo hinh thanh cong!")

    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        num_hands=1,
        min_hand_detection_confidence=0.7,
        min_hand_presence_confidence=0.7,
        min_tracking_confidence=0.7
    )
    detector = vision.HandLandmarker.create_from_options(options)
else:
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7
    )
    mp_draw = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)

# Khởi tạo giá trị ban đầu cho Volume Bar UI
volBar = 400
volPer = 0

print("Dang chay ung dung dieu khien am luong bang tay. Nhan 'q' de thoat.")

while True:
    success, img = cap.read()
    if not success:
        print("Khong the doc camera hoac camera dang duoc su dung boi ung dung khac.")
        break

    # Lật ảnh theo chiều ngang để thao tác tự nhiên hơn (kiểu gương)
    img = cv2.flip(img, 1)
    imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    lmList = []

    if use_tasks_api:
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=imgRGB)
        results = detector.detect(mp_image)
        if results.hand_landmarks:
            h, w, c = img.shape
            hand_landmarks = results.hand_landmarks[0]
            for id, lm in enumerate(hand_landmarks):
                cx, cy = int(lm.x * w), int(lm.y * h)
                lmList.append([id, cx, cy])
            
            # Vẽ các đường nối khớp tay
            for connection in HAND_CONNECTIONS:
                pt1 = (lmList[connection[0]][1], lmList[connection[0]][2])
                pt2 = (lmList[connection[1]][1], lmList[connection[1]][2])
                cv2.line(img, pt1, pt2, (0, 255, 0), 2)

            # Vẽ các điểm mốc bàn tay
            for lm in lmList:
                cv2.circle(img, (lm[1], lm[2]), 5, (255, 0, 255), cv2.FILLED)
    else:
        results = hands.process(imgRGB)
        if results.multi_hand_landmarks:
            for handLms in results.multi_hand_landmarks:
                mp_draw.draw_landmarks(img, handLms, mp_hands.HAND_CONNECTIONS)
                h, w, c = img.shape
                for id, lm in enumerate(handLms.landmark):
                    cx, cy = int(lm.x * w), int(lm.y * h)
                    lmList.append([id, cx, cy])

    if len(lmList) != 0:
        # Lấy tọa độ đầu ngón cái (id 4) và đầu ngón trỏ (id 8)
        x1, y1 = lmList[4][1], lmList[4][2]
        x2, y2 = lmList[8][1], lmList[8][2]
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

        # Vẽ hình tròn và đường nối giữa 2 ngón tay
        cv2.circle(img, (x1, y1), 10, (0, 255, 0), cv2.FILLED)
        cv2.circle(img, (x2, y2), 10, (0, 255, 0), cv2.FILLED)
        cv2.line(img, (x1, y1), (x2, y2), (0, 255, 0), 3)
        cv2.circle(img, (cx, cy), 8, (0, 0, 255), cv2.FILLED)

        # Tính độ dài khoảng cách giữa 2 ngón tay
        length = math.hypot(x2 - x1, y2 - y1)

        # Ánh xạ khoảng cách ngón tay (thường trong dải 20 - 180px) sang dải âm lượng
        vol = np.interp(length, [20, 180], [minVol, maxVol])
        volBar = np.interp(length, [20, 180], [400, 150])
        volPer = np.interp(length, [20, 180], [0, 100])

        # Đặt âm lượng hệ thống
        try:
            volume.SetMasterVolumeLevel(vol, None)
        except Exception:
            pass

        # Đổi màu điểm trung tâm khi chụm ngón tay lại gần sát (dưới 20px)
        if length < 20:
            cv2.circle(img, (cx, cy), 8, (255, 0, 0), cv2.FILLED)

    # -------------------------------------------------------------
    # 3. Vẽ thanh Volume Bar và % lên màn hình
    # -------------------------------------------------------------
    # Khung viền thanh volume
    cv2.rectangle(img, (50, 150), (85, 400), (0, 255, 0), 3)
    # Phần hiển thị mức volume màu xanh lục
    cv2.rectangle(img, (50, int(volBar)), (85, 400), (0, 255, 0), cv2.FILLED)
    # Hiển thị số phần trăm
    cv2.putText(img, f'{int(volPer)} %', (40, 450), 
                cv2.FONT_HERSHEY_COMPLEX, 1, (0, 255, 0), 3)

    cv2.imshow("Hand Tracking Volume Control", img)
    
    # Nhấn 'q' để thoát
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()