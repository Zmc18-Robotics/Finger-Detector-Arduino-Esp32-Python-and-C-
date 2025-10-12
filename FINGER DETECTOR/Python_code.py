# Buka VScode lalu jalankan setelah kode untuk mikrokontroller-mu sudah terupload, dan
# pastikan sambungan kabel usb tetap terkoneksi ya!
 
import cv2
import mediapipe as mp
import serial
import time
import numpy as np
import math

class HandFaceDetectionController:
    def __init__(self, com_port='COM4', baud_rate=115200):
        """
        Inisialisasi Hand and Face Detection Controller
        """
        # Setup MediaPipe untuk tangan
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        
        # Setup MediaPipe untuk wajah
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        
        self.mp_draw = mp.solutions.drawing_utils
        
        # Setup Serial Communication
        try:
            self.serial_conn = serial.Serial(com_port, baud_rate, timeout=1)
            time.sleep(2)  # Wait untuk ESP32 reset
            print(f"Connected to ESP32 on {com_port}")
        except Exception as e:
            print(f"Error connecting to ESP32: {e}")
            self.serial_conn = None
        
        # Setup Camera
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        # Variabel untuk deteksi mengangguk
        self.head_positions = []
        self.max_head_positions = 15  # Buffer untuk tracking posisi kepala
        self.nod_threshold = 0.02  # Threshold untuk mendeteksi gerakan mengangguk
        self.last_nod_time = 0
        self.nod_cooldown = 2.0  # Cooldown 2 detik antar deteksi mengangguk
        
        print("Hand and Face Detection Controller initialized!")
        print("Controls:")
        print("- Show hand to camera to control finger LEDs")
        print("- Nod your head to blink LED on pin 5 (3 times)")
        print("- Press 'q' to quit")
        print("- Press 's' to toggle serial communication")
    
    def count_fingers(self, landmarks):
        """
        Menghitung jumlah jari yang terbuka menggunakan landmark positions
        """
        finger_landmarks = [
            [4, 3, 2],    # Thumb: tip, ip, mcp
            [8, 6, 5],    # Index: tip, pip, mcp  
            [12, 10, 9],  # Middle: tip, pip, mcp
            [16, 14, 13], # Ring: tip, pip, mcp
            [20, 18, 17]  # Pinky: tip, pip, mcp
        ]
        
        fingers_up = []
        
        # Deteksi untuk ibu jari (Thumb)
        thumb_tip = landmarks[finger_landmarks[0][0]]
        thumb_mcp = landmarks[finger_landmarks[0][2]]
        
        wrist = landmarks[0]
        middle_mcp = landmarks[finger_landmarks[2][2]]
        
        is_right_hand = middle_mcp.x > wrist.x
        
        if is_right_hand:
            thumb_open = thumb_tip.x > thumb_mcp.x
        else:
            thumb_open = thumb_tip.x < thumb_mcp.x
        
        thumb_vertical_check = abs(thumb_tip.y - thumb_mcp.y) > 0.02
        fingers_up.append(1 if thumb_open and thumb_vertical_check else 0)
        
        # Deteksi untuk jari lainnya
        for i in range(1, 5):
            tip = landmarks[finger_landmarks[i][0]]
            pip = landmarks[finger_landmarks[i][1]]
            mcp = landmarks[finger_landmarks[i][2]]
            
            finger_straight = (tip.y < pip.y) and (pip.y < mcp.y)
            finger_extended = abs(tip.y - mcp.y) > 0.04
            
            fingers_up.append(1 if finger_straight and finger_extended else 0)
        
        return sum(fingers_up)
    
    def detect_nod(self, face_landmarks):
        """
        Deteksi gerakan mengangguk berdasarkan pergerakan titik hidung
        """
        # Gunakan titik hidung (landmark 1) untuk tracking
        nose_tip = face_landmarks[1]
        current_y = nose_tip.y
        
        # Tambahkan posisi saat ini ke buffer
        self.head_positions.append(current_y)
        
        # Pertahankan ukuran buffer
        if len(self.head_positions) > self.max_head_positions:
            self.head_positions.pop(0)
        
        # Perlu minimal 10 frame untuk deteksi
        if len(self.head_positions) < 10:
            return False
        
        # Analisis pergerakan dalam buffer
        recent_positions = self.head_positions[-10:]
        
        # Code by Zmc18_Robotics, @mc.zminecrafter_18
        # Cari pola naik-turun (mengangguk)
        peaks = []  # Posisi maksimum (kepala ke atas)
        valleys = []  # Posisi minimum (kepala ke bawah)
        
        for i in range(1, len(recent_positions) - 1):
            # Peak (titik tertinggi lokal)
            if (recent_positions[i] > recent_positions[i-1] and 
                recent_positions[i] > recent_positions[i+1]):
                peaks.append((i, recent_positions[i]))
            
            # Valley (titik terendah lokal)
            if (recent_positions[i] < recent_positions[i-1] and 
                recent_positions[i] < recent_positions[i+1]):
                valleys.append((i, recent_positions[i]))
        
        # Deteksi pola mengangguk: harus ada minimal 1 peak dan 1 valley
        if len(peaks) >= 1 and len(valleys) >= 1:
            # Cari peak dan valley terakhir
            last_peak = peaks[-1][1] if peaks else 0
            last_valley = valleys[-1][1] if valleys else 0
            
            # Hitung amplitude pergerakan
            movement_amplitude = abs(last_peak - last_valley)
            
            # Deteksi mengangguk jika amplitude cukup besar
            if movement_amplitude > self.nod_threshold:
                current_time = time.time()
                # Cek cooldown
                if current_time - self.last_nod_time > self.nod_cooldown:
                    self.last_nod_time = current_time
                    print(f"Nod detected! Amplitude: {movement_amplitude:.4f}")
                    return True
        
        return False
    
    def send_to_esp32(self, finger_count, nod_detected=False):
        """
        Mengirim data ke ESP32
        Format: "finger_count,nod_status\n"
        """
        if self.serial_conn and self.serial_conn.is_open:
            try:
                nod_flag = 1 if nod_detected else 0
                message = f"{finger_count},{nod_flag}\n"
                self.serial_conn.write(message.encode())
                return True
            except Exception as e:
                print(f"Error sending data: {e}")
                return False
        return False
    
    def draw_info(self, image, finger_count, fps, finger_states=None, face_detected=False, nod_detected=False):
        """
        Menggambar informasi pada frame (tanpa simbol LED)
        """
        # Background untuk text
        cv2.rectangle(image, (10, 10), (450, 180), (0, 0, 0), -1)
        
        # Finger count
        cv2.putText(image, f'Jari terdeteksi: {finger_count}', (20, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # FPS
        cv2.putText(image, f'FPS: {int(fps)}', (20, 70), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # LED Status tanpa simbol
        led_on_count = finger_count
        cv2.putText(image, f'LED Jari ({led_on_count}/5)', (20, 100), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # Individual finger status
        if finger_states:
            finger_names = ['T', 'I', 'M', 'R', 'P']
            finger_status = ' '.join([f"{name}={int(state)}" 
                                   for name, state in zip(finger_names, finger_states)])
            cv2.putText(image, f'Fingers: {finger_status}', (20, 130), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
        
        # Face detection status
        face_color = (0, 255, 0) if face_detected else (0, 0, 255)
        face_text = "TERDETEKSI" if face_detected else "TIDAK TERDETEKSI"
        cv2.putText(image, f'Wajah: {face_text}', (20, 160), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, face_color, 2)
        
        # Nod detection status
        if nod_detected:
            cv2.putText(image, 'TIDAK TERDETEKSI! LED Pin 5 Berkedip!', (250, 160), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    
    def get_finger_states(self, landmarks):
        """
        Mendapatkan status individual setiap jari untuk debugging
        """
        finger_landmarks = [
            [4, 3, 2], [8, 6, 5], [12, 10, 9], [16, 14, 13], [20, 18, 17]
        ]
        
        fingers_up = []
        
        # Thumb
        thumb_tip = landmarks[finger_landmarks[0][0]]
        thumb_mcp = landmarks[finger_landmarks[0][2]]
        wrist = landmarks[0]
        middle_mcp = landmarks[finger_landmarks[2][2]]
        is_right_hand = middle_mcp.x > wrist.x
        
        if is_right_hand:
            thumb_open = thumb_tip.x > thumb_mcp.x
        else:
            thumb_open = thumb_tip.x < thumb_mcp.x
        
        thumb_vertical_check = abs(thumb_tip.y - thumb_mcp.y) > 0.02
        fingers_up.append(thumb_open and thumb_vertical_check)
        
        # Other fingers
        for i in range(1, 5):
            tip = landmarks[finger_landmarks[i][0]]
            pip = landmarks[finger_landmarks[i][1]]
            mcp = landmarks[finger_landmarks[i][2]]
            
            finger_straight = (tip.y < pip.y) and (pip.y < mcp.y)
            finger_extended = abs(tip.y - mcp.y) > 0.04
            
            fingers_up.append(finger_straight and finger_extended)
        
        return fingers_up
    
    def run(self):
        """
        Main loop untuk deteksi tangan dan wajah
        """
        prev_time = 0
        prev_finger_count = -1
        serial_enabled = True
        
        while True:
            success, image = self.cap.read()
            if not success:
                print("Failed to read from camera")
                break
            
            # Flip image horizontally untuk mirror effect
            image = cv2.flip(image, 1)
            
            # Convert BGR to RGB
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Process tangan dengan MediaPipe
            hand_results = self.hands.process(rgb_image)
            
            # Process wajah dengan MediaPipe
            face_results = self.face_mesh.process(rgb_image)
            
            # Code by Zmc18_Robotics, @mc.zminecrafter_18
            finger_count = 0
            finger_states = None
            face_detected = False
            nod_detected = False
            
            # Proses deteksi tangan
            if hand_results.multi_hand_landmarks:
                for hand_landmarks in hand_results.multi_hand_landmarks:
                    # Gambar landmarks tangan
                    self.mp_draw.draw_landmarks(
                        image, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                    
                    # Hitung jumlah jari dan status individual
                    finger_count = self.count_fingers(hand_landmarks.landmark)
                    finger_states = self.get_finger_states(hand_landmarks.landmark)
            
            # Proses deteksi wajah
            if face_results.multi_face_landmarks:
                face_detected = True
                for face_landmarks in face_results.multi_face_landmarks:
                    # Deteksi mengangguk
                    nod_detected = self.detect_nod(face_landmarks.landmark)
                    
                    # Gambar beberapa key points wajah (hidung, mata, mulut)
                    key_points = [1, 33, 263, 61, 291, 199]  # hidung, mata kiri/kanan, mulut
                    for point_id in key_points:
                        landmark = face_landmarks.landmark[point_id]
                        x = int(landmark.x * image.shape[1])
                        y = int(landmark.y * image.shape[0])
                        cv2.circle(image, (x, y), 3, (0, 255, 0), -1)
            
            # Kirim data ke ESP32
            if serial_enabled and (finger_count != prev_finger_count or nod_detected):
                if self.send_to_esp32(finger_count, nod_detected):
                    if nod_detected:
                        print(f"Sent to ESP32: {finger_count} fingers + NOD detected")
                    else:
                        print(f"Sent to ESP32: {finger_count} fingers")
                prev_finger_count = finger_count
            
            # Hitung FPS
            curr_time = time.time()
            fps = 1 / (curr_time - prev_time) if prev_time != 0 else 0
            prev_time = curr_time
            
            # Gambar informasi
            self.draw_info(image, finger_count, fps, finger_states, face_detected, nod_detected)
            
            # Tampilkan image
            cv2.imshow('Hand & Face Detection - ESP32 LED Controller', image)
            
            # Handle key presses
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                serial_enabled = not serial_enabled
                status = "ENABLED" if serial_enabled else "DISABLED"
                print(f"Serial communication {status}")
        
        self.cleanup()
    
    def cleanup(self):
        """
        Cleanup resources
        """
        # Matikan semua LED sebelum close
        if self.serial_conn and self.serial_conn.is_open:
            self.send_to_esp32(0, False)
            time.sleep(0.1)
            self.serial_conn.close()
        
        self.cap.release()
        cv2.destroyAllWindows()
        print("Resources cleaned up. Goodbye!")

def main():
    """
    Main function
    """
    print("=== ESP32 Hand & Face Detection LED Controller ===")
    print("Initializing...")
    # Code by Zmc18_Robotics, @mc.zminecrafter_18
    try:
        controller = HandFaceDetectionController(com_port='COM4')
        controller.run()
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
