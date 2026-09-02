import cv2
import mediapipe as mp
from collections import deque
import numpy as np

# Robust import of mediapipe solutions for cross-platform and Python version compatibility
try:
    import mediapipe.python.solutions.hands as mp_hands
    import mediapipe.python.solutions.drawing_utils as mp_draw
except (ImportError, AttributeError):
    try:
        mp_hands = mp.solutions.hands
        mp_draw = mp.solutions.drawing_utils
    except AttributeError:
        from mediapipe.solutions import hands as mp_hands, drawing_utils as mp_draw

class HandTracker:
    def __init__(self, mode=False, max_hands=1, detection_con=0.7, track_con=0.5):
        self.mode = mode
        self.max_hands = max_hands
        self.detection_con = detection_con
        self.track_con = track_con

        self.mp_hands = mp_hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=self.mode,
            max_num_hands=self.max_hands,
            min_detection_confidence=self.detection_con,
            min_tracking_confidence=self.track_con
        )
        self.mp_draw = mp_draw
        self.tip_ids = [4, 8, 12, 16, 20]
        
        # History for motion detection
        self.history = deque(maxlen=10)

    def find_hands(self, img, draw=True):
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.results = self.hands.process(img_rgb)

        if self.results.multi_hand_landmarks:
            for hand_lms in self.results.multi_hand_landmarks:
                if draw:
                    self.mp_draw.draw_landmarks(img, hand_lms, self.mp_hands.HAND_CONNECTIONS)
        return img

    def find_position(self, img, hand_no=0, draw=True):
        self.lm_list = []
        if self.results.multi_hand_landmarks:
            my_hand = self.results.multi_hand_landmarks[hand_no]
            for id, lm in enumerate(my_hand.landmark):
                h, w, c = img.shape
                cx, cy = int(lm.x * w), int(lm.y * h)
                self.lm_list.append([id, cx, cy])
                if draw:
                    cv2.circle(img, (cx, cy), 15, (255, 0, 255), cv2.FILLED)
            
            # Store index finger tip position (ID 8) in history
            self.history.append((self.lm_list[8][1], self.lm_list[8][2]))
        else:
            self.history.clear()
            
        return self.lm_list

    def fingers_up(self):
        if not self.lm_list: return [0,0,0,0,0]
        fingers = []
        # Thumb
        if self.lm_list[self.tip_ids[0]][1] < self.lm_list[self.tip_ids[0] - 1][1]:
            fingers.append(1)
        else:
            fingers.append(0)

        # 4 Fingers
        for id in range(1, 5):
            if self.lm_list[self.tip_ids[id]][2] < self.lm_list[self.tip_ids[id] - 2][2]:
                fingers.append(1)
            else:
                fingers.append(0)
        return fingers

    def get_gesture(self, fingers):
        if not self.lm_list: return "NONE"
        
        # Open Palm Navigation (5 fingers up)
        if fingers == [1, 1, 1, 1, 1]:
            if len(self.history) == 10:
                dx = self.history[-1][0] - self.history[0][0]
                dy = self.history[-1][1] - self.history[0][1]
                
                if abs(dx) > 100 and abs(dy) < 50:
                    if dx < 0: return "SWIPE_LEFT"
                    else: return "SWIPE_RIGHT"
            return "NONE"

        # Closed Fist -> CLEAR
        if fingers == [0, 0, 0, 0, 0]:
            return "CLEAR"

        # Static Gestures
        if fingers == [0, 1, 0, 0, 0]:
            return "DRAW"
        elif fingers == [0, 1, 1, 0, 0]:
            return "ERASE"
        elif fingers == [0, 1, 1, 1, 0]:
            return "COLOR"
            
        return "NONE"
