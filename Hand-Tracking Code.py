
import cv2
import win32gui
import win32con
import mediapipe as mp
import time
import serial
import tkinter as tk
from tkinter import messagebox, Toplevel, Label
from PIL import Image, ImageTk  # Correct import for PIL.Image

ser = None

# Function to center the Tkinter main window
def center_window(window):
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")

# Function to initialize serial connection with a popup
def init_serial():
    global ser

    # Create a popup window for detecting COM port
    popup = Toplevel(root)
    popup.title("Detecting COM Port")
    popup.geometry("300x100")
    center_window(popup)
    label = Label(popup, text="Detecting COM Port...\nPlease wait.", font=("Arial", 12))
    label.pack(pady=20)
    popup.update()

    # Check if the camera is available
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        popup.destroy()
        messagebox.showerror("Error", "No camera found! Please check your camera.")
        return

    # Try detecting the COM port dynamically
    detected = False
    try:
        for port in range(1, 256):  # Loop through possible COM ports (COM1 to COM255)
            try:
                ser = serial.Serial(f'COM{port}', 9600, timeout=1)
                time.sleep(2)  # Give time for the device to initialize
                ser.write(b'CAMERA_MODE\n')  # Enter camera mode
                detected = True
                break  # Exit loop if a port is successfully detected
            except serial.SerialException:
                continue  # Try the next port

        popup.destroy()

        if detected:
            messagebox.showinfo("Info", f"COM Port detected: COM{port}. Camera turned on.")
            run_camera(popup)  # Pass popup to close it once the camera is started
        else:
            messagebox.showerror("Error", "No COM Port detected. Please check the connection.")
    finally:
        cap.release()  # Make sure to release the camera


# Function to display how to use the system
def show_how_to_use():
    # Create a Toplevel window to show the image
    tutorial_window = Toplevel(root)
    tutorial_window.title("How to Use")

    # Load the image
    img_path = "tutorial.png"  # Replace with the path to your image
    img = Image.open(img_path)

    # Get the size of the image and define maximum width/height
    max_width = 800  # Set your desired maximum width
    max_height = 600  # Set your desired maximum height

    img_width, img_height = img.size  # Original size

    # Resize the image while maintaining the aspect ratio
    if img_width > max_width or img_height > max_height:
        aspect_ratio = img_width / img_height
        if img_width > img_height:
            new_width = max_width
            new_height = int(max_width / aspect_ratio)
        else:
            new_height = max_height
            new_width = int(max_height * aspect_ratio)
    else:
        new_width = img_width
        new_height = img_height

    # Resize the image using LANCZOS resampling
    img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    img_tk = ImageTk.PhotoImage(img_resized)

    # Resize the window to fit the image
    tutorial_window.geometry(f"{new_width}x{new_height}")
    center_window(tutorial_window)

    # Create a label to display the image
    image_label = tk.Label(tutorial_window, image=img_tk)
    image_label.image = img_tk  # Keep a reference to the image object
    image_label.pack(padx=10, pady=10)

    # Optional: Close the window when clicked outside
   # tutorial_window.grab_set()  # Prevent interaction with the main window
    tutorial_window.wait_window()  # Wait for the window to be closed


# Main application logic
def run_camera(popup):
    global ser

    # Initialize MediaPipe and Serial
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(max_num_hands=1)
    mp_drawing = mp.solutions.drawing_utils
    cap = cv2.VideoCapture(0)

    # Get OpenCV window handle and remove maximize/close buttons
    cv2.namedWindow("Gesture Control", cv2.WINDOW_NORMAL)

    hwnd = win32gui.FindWindow(None, "Gesture Control")
    if hwnd:
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style & ~win32con.WS_MAXIMIZEBOX & ~win32con.WS_SYSMENU)

    def resize_with_aspect_ratio(frame, target_width, target_height):
        original_height, original_width = frame.shape[:2]
        aspect_ratio = original_width / original_height

        if target_width / target_height > aspect_ratio:
            # Constrain by height
            new_height = target_height
            new_width = int(new_height * aspect_ratio)
        else:
            # Constrain by width
            new_width = target_width
            new_height = int(new_width / aspect_ratio)

        resized_frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
        # Add black padding if necessary
        padded_frame = cv2.copyMakeBorder(
            resized_frame,
            (target_height - new_height) // 2,
            (target_height - new_height) - (target_height - new_height) // 2,
            (target_width - new_width) // 2,
            (target_width - new_width) - (target_width - new_width) // 2,
            cv2.BORDER_CONSTANT,
            value=[0, 0, 0],
        )
        return padded_frame

    # Function to count fingers
    def count_fingers(hand_landmarks):
        finger_count = 0
        finger_tips = [4, 8, 12, 16, 20]
        thumb_tip_y = hand_landmarks.landmark[4].y
        thumb_base_y = hand_landmarks.landmark[3].y

        # Check if thumb is extended
        if thumb_tip_y < thumb_base_y - 0.05:
            finger_count += 1

        # Check for each finger (index, middle, ring, and pinky) if it is extended
        for tip_index in finger_tips[1:]:
            if hand_landmarks.landmark[tip_index].y < hand_landmarks.landmark[tip_index - 2].y:
                finger_count += 1

        return finger_count

    # Variables to maintain fan state and display message
    fan_on = False
    last_message = ""
    last_message_color = (0, 255, 0)
    finger_count_history = []  # To keep a history of finger counts for debouncing
    history_length = 5  # Number of frames for consistent gesture

    hand_tracking_enabled = True  # Hand-tracking is ON by default

    try:
        while cap.isOpened():
            success, image = cap.read()
            if not success:
                break

            image = cv2.flip(image, 1)
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = hands.process(image_rgb)
            if hand_tracking_enabled:
                results = hands.process(image_rgb)

                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        mp_drawing.draw_landmarks(image, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                        finger_count = count_fingers(hand_landmarks)

                        # Append the current finger count to the history
                        finger_count_history.append(finger_count)

                        # Maintain only the latest `history_length` values
                        if len(finger_count_history) > history_length:
                            finger_count_history.pop(0)

                        # Check if COM port is still open and close if not
                        if not ser.is_open:
                            messagebox.showwarning("Warning", "COM Port lost! Closing Camera.")
                            popup.destroy()  # Close the popup
                            cap.release()
                            cv2.destroyAllWindows()
                            break

                        # Check if the camera is still available (if it's unplugged or disabled)
                        if not cap.isOpened():
                            ser.write(b'EXIT\n')
                            messagebox.showwarning("Warning", "Camera disconnected or disabled!")
                            popup.destroy()  # Close the popup
                            cap.release()
                            cv2.destroyAllWindows()
                            break

                        # Check if we have a consistent finger count over the history
                        if finger_count_history.count(finger_count) == history_length:
                            # Update fan state and display message based on finger count
                            if finger_count == 5 and not fan_on:
                                fan_on = True
                                ser.write(b'1\n')
                                last_message = "Fan ON"
                                last_message_color = (0, 255, 0)

                            elif finger_count == 0 and fan_on:
                                fan_on = False
                                ser.write(b'0\n')
                                last_message = "Fan OFF"
                                last_message_color = (0, 0, 255)

                            elif fan_on:
                                if finger_count == 1:
                                    ser.write(b'1\n')
                                    last_message = "Fan Speed 1"
                                    last_message_color = (255, 0, 0)
                                elif finger_count == 2:
                                    ser.write(b'2\n')
                                    last_message = "Fan Speed 2"
                                    last_message_color = (255, 0, 0)
                                elif finger_count == 3:
                                    ser.write(b'3\n')
                                    last_message = "Fan Speed 3"
                                    last_message_color = (255, 0, 0)

            # Get window size
            window_width = win32gui.GetWindowRect(hwnd)[2] - win32gui.GetWindowRect(hwnd)[0]
            window_height = win32gui.GetWindowRect(hwnd)[3] - win32gui.GetWindowRect(hwnd)[1]

            if hand_tracking_enabled:
                cv2.putText(image, "Press [X] to Disable Tracking", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            (0, 0, 0), 2)
            else:
                cv2.putText(image, "Press [X] to Enable Tracking", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            (0, 0, 0), 2)

            # Add the text to the image before resizing
            cv2.putText(image, last_message, (10, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.9, last_message_color, 2)
            cv2.putText(image, "Press [Esc] to Exit", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

            # Resize frame while maintaining aspect ratio
            resized_frame = resize_with_aspect_ratio(image, window_width, window_height)

            # Show the final resized frame with text
            cv2.imshow("Gesture Control", resized_frame)

            # Handle the key press (Esc key for exit)
            key = cv2.waitKey(5) & 0xFF  # Wait for a key press and capture it
            if key == 27:  # ESC key
                ser.write(b'EXIT\n')
                break
            elif key == ord('x') or key == ord('X'):  # Toggle hand-tracking with 'X'
                hand_tracking_enabled = not hand_tracking_enabled  # Toggle state

    except KeyboardInterrupt:
        print("Program terminated by user.")
        if ser:  # Ensure ser is initialized before writing
            ser.write(b'EXIT\n')
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if ser:  # Ensure ser is initialized before closing
            ser.write(b'EXIT\n')
            ser.close()

# Tkinter GUI Setup
root = tk.Tk()
root.title("Hand-Gesture Control System")

# Load the image to be displayed
img_path = "image.png"  # Replace with your image path
img = Image.open(img_path)
img = img.resize((230, 200))  # Resize image
img_tk = ImageTk.PhotoImage(img)

# Display the image in Tkinter window
image_label = tk.Label(root, image=img_tk)
image_label.pack(pady=10)

# Function to remove the maximize button
def remove_maximize_button():
    hwnd = win32gui.FindWindow(None, "Hand-Gesture Control System")
    if hwnd:
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style & ~win32con.WS_MAXIMIZEBOX)

# Call the function after the window is initialized
root.after(10, remove_maximize_button)

# Button Frame for horizontal arrangement
button_frame = tk.Frame(root)
button_frame.pack(pady=8)

# Start Button to initialize serial and camera
start_button = tk.Button(button_frame,
                         text="Start Camera",
                         command=init_serial,
                         font=("Arial", 14),
                         bg="#36ad3a",
                         fg="white")
start_button.pack(side="left", padx=10)

# How to Use button
how_to_use_button = tk.Button(button_frame,
                              text="How to Use",
                              command=show_how_to_use,
                              font=("Arial", 14),
                              bg="#4387bf",
                              fg="white")
how_to_use_button.pack(side="left", padx=10)

root.geometry("400x300")
center_window(root)
root.mainloop()
