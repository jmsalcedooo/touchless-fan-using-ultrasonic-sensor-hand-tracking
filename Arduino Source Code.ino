#include <LiquidCrystal_I2C.h>
#include <avr/wdt.h>
#include <EEPROM.h> // Include EEPROM library

LiquidCrystal_I2C lcd(0x27, 16, 2);

const int trigPin = 9;
const int echoPin = 10;
const int fanControlPin = 4; // MOSFET Gate control
const int fanPwmPin = 3;     // Fan PWM (2510) control

bool fanState = false; // Variable to track the fan's state
int fanSpeed = 0;      // Variable to track the fan's PWM speed (0 to 255)
int fingerCount = 0;
bool cameraMode = false;

void setup() {
  Serial.begin(9600);
  lcd.begin(16, 2);
  lcd.backlight();
  
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(fanControlPin, OUTPUT); // MOSFET Gate
  pinMode(fanPwmPin, OUTPUT);     // PWM control for fan

  // Load fan state and speed from EEPROM
  fanState = EEPROM.read(0);              // Read fan state from address 0
  fanSpeed = EEPROM.read(1);              // Read fan speed from address 1
  fanSpeed = constrain(fanSpeed, 0, 255); // Ensure valid PWM range
  digitalWrite(fanControlPin, fanState ? HIGH : LOW);
  analogWrite(fanPwmPin, fanSpeed);

  lcd.setCursor(0, 0);
  lcd.print("Refreshing...");
  delay(1000);
  lcd.clear();
}

void loop() {
  // Handle Serial Commands for Camera Mode
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    if (command == "CAMERA_MODE") {
      cameraMode = true;
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("Camera Mode ON");
      setFanState(false, 0); // Turn off fan
    } else if (command == "EXIT") {
      cameraMode = false;
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("Ultrasonic Mode");
    } else if (cameraMode) {
      fingerCount = command.toInt();
      int pwmValue = 0;

      if (fingerCount == 1) {
        pwmValue = 85; // Low speed
        lcd.setCursor(0, 1);
        lcd.print("Speed: 1 x   ");
      } else if (fingerCount == 2) {
        pwmValue = 170; // Medium speed
        lcd.setCursor(0, 1);
        lcd.print("Speed: 2 x   ");
      } else if (fingerCount == 3) {
        pwmValue = 255; // Max speed
        lcd.setCursor(0, 1);
        lcd.print("Speed: 3 x   ");
      } else {
        pwmValue = 0; // Turn off fan
        lcd.setCursor(0, 1);
        lcd.print("Speed: OFF   ");
      }

      if (pwmValue > 0) {
        setFanState(true, pwmValue); // Turn on MOSFET with speed
      } else {
        setFanState(false, 0); // Turn off MOSFET
      }
    }
  }

  // Ultrasonic Mode
  if (!cameraMode) {
    digitalWrite(trigPin, LOW);
    delayMicroseconds(2);
    digitalWrite(trigPin, HIGH);
    delayMicroseconds(10);
    digitalWrite(trigPin, LOW);

    long duration = pulseIn(echoPin, HIGH, 30000);
    float distanceCm = (duration > 0) ? duration * 0.034 / 2 : -1;

    int pwmValue = 0;
    int speed = 0;

    if (distanceCm > 100 || distanceCm < 0) {
      setFanState(false, 0); // Turn off fan
      speed = 0;
    } else {
      if (distanceCm > 90) {
        pwmValue = 85; // Low speed
        speed = 1;
      } else if (distanceCm > 70) {
        pwmValue = 170; // Medium speed
        speed = 2;
      } else {
        pwmValue = 255; // High speed
        speed = 3;
      }
      setFanState(true, pwmValue); // Turn on fan with speed
    }
           
    if (speed == 0) {
      lcd.setCursor(0, 0);
      lcd.print("Dist: Unreadable");
      lcd.setCursor(0, 1);
      lcd.print("Fan Speed: OFF");
    } else {
      lcd.setCursor(0, 0);
      lcd.print("Dist: ");
      lcd.print(distanceCm, 2);
      lcd.print(" cm         ");

      lcd.setCursor(0, 1);
      lcd.print("Fan Speed: ");
      lcd.print(speed);
      lcd.print(" x");
      delay(2000);
    }
     
  }
}

// Function to set fan state and speed, and save them to EEPROM
void setFanState(bool state, int speed) {
  fanState = state;
  fanSpeed = speed;
  digitalWrite(fanControlPin, state ? HIGH : LOW);
  analogWrite(fanPwmPin, speed);

  EEPROM.update(0, state); // Save state to EEPROM
  EEPROM.update(1, speed); // Save speed to EEPROM
}