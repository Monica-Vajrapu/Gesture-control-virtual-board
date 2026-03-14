import mediapipe as mp
print("Import mediapipe: Success")
try:
    hands = mp.solutions.hands
    print("Access mp.solutions.hands: Success")
except AttributeError:
    print("Access mp.solutions.hands: AttributeError")
except Exception as e:
    print(f"Access mp.solutions.hands: Error: {e}")

try:
    draw = mp.solutions.drawing_utils
    print("Access mp.solutions.drawing_utils: Success")
except AttributeError:
    print("Access mp.solutions.drawing_utils: AttributeError")
except Exception as e:
    print(f"Access mp.solutions.drawing_utils: Error: {e}")
