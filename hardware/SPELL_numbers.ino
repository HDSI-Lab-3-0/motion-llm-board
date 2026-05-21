#include <AccelStepper.h>

// =========================
// PIN CONFIG
// =========================
const int STEP_X = 3;
const int DIR_X  = 6;

const int STEP_Y = 2;
const int DIR_Y  = 5;

const bool USE_ENABLE_PIN = true;
const int ENABLE_PIN = 8;

// Integrated homing switches
const int switchPinY = 4;
const int switchPinX = 7;

// =========================
// MACHINE CALIBRATION
// =========================
float stepsPerMmX = 80.0;
float stepsPerMmY = 80.0;

// SAFE WORKING BOUNDS
float xMinMm = -8.0;
float xMaxMm = 8.0;
float yMinMm = -30.0;
float yMaxMm = 40.0;

// TRUE PHYSICAL HOME SWITCH TRIGGER LOCATIONS
float yHomeSwitchMm = -33.0;
float xHomeSwitchMm = -9.0;

// Resting visual center after homing
float xCenterMm = -7.0;
float yCenterMm = 3.0;

// Motion tuning
float maxSpeedStepsX = 80.0;
float accelStepsX    = 20.0;

float maxSpeedStepsY = 260.0;
float accelStepsY    = 100.0;

// Homing tuning
float homeSpeedStepsX = 80.0;
float homeSpeedStepsY = 200.0;

float homeBackoffMmX  = 2.0;
float homeBackoffMmY  = 2.0;

// Homing search directions
int homeDirectionX = 1;
int homeDirectionY = -1;

// Flip only if direction is reversed during normal motion
const bool invertX = true;
const bool invertY = false;

// Homing safety / debounce
unsigned long homeTimeoutMs = 60000;
unsigned long stablePressMs = 20;

// =========================
// FORWARD DECLARATIONS
// =========================
void monitorSwitchChanges();
void moveBlockingTo(float x, float y);
void goYes();
void goNo();
void goCenter();

// =========================
// LETTER / NUMBER COORDINATES
// =========================
struct Target {
  char letter;
  float x;
  float y;
};

Target letterMap[] = {
  {'A', 2, 38},
  {'B', 2, 32},
  {'C', 3, 26},
  {'D', 3, 22},
  {'E', 3, 16},
  {'F', 3, 10},
  {'G', 3, 5},
  {'H', 3, -1},
  {'I', 3, -6},
  {'J', 3, -11},
  {'K', 3, -15},
  {'L', 3, -22},
  {'M', 2, -30},

  {'N', -3, 38},
  {'O', -3, 32},
  {'P', -2, 27},
  {'Q', -2, 21},
  {'R', -2, 15},
  {'S', -2, 10},
  {'T', -2, 5},
  {'U', -2, -1},
  {'V', -2, -6},
  {'W', -2, -12},
  {'X', -2, -19},
  {'Y', -3, -25},
  {'Z', -3, -30}
};

const int letterCount = sizeof(letterMap) / sizeof(letterMap[0]);

Target numberMap[] = {
  {'1', -7, 30},
  {'2', -7, 24},
  {'3', -7, 19},
  {'4', -7, 13},
  {'5', -7, 7},
  {'6', -7, 1},
  {'7', -7, -5},
  {'8', -7, -11},
  {'9', -7, -16},
  {'0', -7, -22}
};

const int numberCount = sizeof(numberMap) / sizeof(numberMap[0]);

// Special targets
float yesX = 7.0;
float yesY = 33.0;

float noX = 7.0;
float noY = -25.0;

// =========================
// STEPPER OBJECTS
// =========================
AccelStepper stepperX(AccelStepper::DRIVER, STEP_X, DIR_X);
AccelStepper stepperY(AccelStepper::DRIVER, STEP_Y, DIR_Y);

// =========================
// SERIAL BUFFER / STATE
// =========================
char inputBuffer[100];
uint8_t inputIndex = 0;

bool xKnown = false;
bool yKnown = false;

int lastSwitchStateX = HIGH;
int lastSwitchStateY = HIGH;

// =========================
// HELPERS
// =========================
long mmToStepsX(float mm) {
  float signedMm = invertX ? -mm : mm;
  return lround(signedMm * stepsPerMmX);
}

long mmToStepsY(float mm) {
  float signedMm = invertY ? -mm : mm;
  return lround(signedMm * stepsPerMmY);
}

float stepsToMmX(long steps) {
  float mm = (float)steps / stepsPerMmX;
  return invertX ? -mm : mm;
}

float stepsToMmY(long steps) {
  float mm = (float)steps / stepsPerMmY;
  return invertY ? -mm : mm;
}

float currentXmm() {
  return stepsToMmX(stepperX.currentPosition());
}

float currentYmm() {
  return stepsToMmY(stepperY.currentPosition());
}

bool fullPositionKnown() {
  return xKnown && yKnown;
}

bool inBounds(float x, float y) {
  return (x >= xMinMm && x <= xMaxMm &&
          y >= yMinMm && y <= yMaxMm);
}

float clampf(float v, float lo, float hi) {
  if (v < lo) return lo;
  if (v > hi) return hi;
  return v;
}

bool switchPressedX() {
  return digitalRead(switchPinX) == LOW;
}

bool switchPressedY() {
  return digitalRead(switchPinY) == LOW;
}

bool isAlphaNumeric(char c) {
  return ((c >= 'A' && c <= 'Z') ||
          (c >= 'a' && c <= 'z') ||
          (c >= '0' && c <= '9'));
}

void applyMotionSettings() {
  stepperX.setMaxSpeed(maxSpeedStepsX);
  stepperX.setAcceleration(accelStepsX);
  stepperX.setMinPulseWidth(2);

  stepperY.setMaxSpeed(maxSpeedStepsY);
  stepperY.setAcceleration(accelStepsY);
  stepperY.setMinPulseWidth(2);
}

void enableMotors() {
  if (USE_ENABLE_PIN) {
    digitalWrite(ENABLE_PIN, LOW);
  }
  stepperX.enableOutputs();
  stepperY.enableOutputs();
}

void disableMotors() {
  stepperX.disableOutputs();
  stepperY.disableOutputs();
  if (USE_ENABLE_PIN) {
    digitalWrite(ENABLE_PIN, HIGH);
  }
}

void reportPosition() {
  Serial.print("POS ");

  if (xKnown) Serial.print(currentXmm(), 2);
  else Serial.print("X?");

  Serial.print(" ");

  if (yKnown) Serial.println(currentYmm(), 2);
  else Serial.println("Y?");
}

void reportSwitches() {
  Serial.print("X ");
  Serial.print(switchPressedX() ? "PRESSED" : "RELEASED");
  Serial.print(" | Y ");
  Serial.println(switchPressedY() ? "PRESSED" : "RELEASED");
}

void zeroAllHere() {
  stepperX.setCurrentPosition(0);
  stepperY.setCurrentPosition(0);
  xKnown = true;
  yKnown = true;
  Serial.println("OK ZEROALL");
  reportPosition();
}

void zeroXHere() {
  stepperX.setCurrentPosition(0);
  xKnown = true;
  Serial.println("OK ZEROX");
  reportPosition();
}

void zeroYHere() {
  stepperY.setCurrentPosition(0);
  yKnown = true;
  Serial.println("OK ZEROY");
  reportPosition();
}

void moveBlockingTo(float x, float y) {
  if (!fullPositionKnown()) {
    Serial.println("ERR position_unknown_use_HOMEALL_or_ZEROALL");
    return;
  }

  if (!inBounds(x, y)) {
    Serial.println("ERR out_of_bounds");
    return;
  }

  stepperX.moveTo(mmToStepsX(x));
  stepperY.moveTo(mmToStepsY(y));

  Serial.print("OK MOVING ");
  Serial.print(x, 2);
  Serial.print(" ");
  Serial.println(y, 2);

  while (stepperX.distanceToGo() != 0 || stepperY.distanceToGo() != 0) {
    stepperX.run();
    stepperY.run();
    monitorSwitchChanges();
  }

  Serial.print("DONE ");
  Serial.print(currentXmm(), 2);
  Serial.print(" ");
  Serial.println(currentYmm(), 2);
}

void goToMm(float x, float y) {
  moveBlockingTo(x, y);
}

void goCenter() {
  moveBlockingTo(xCenterMm, yCenterMm);
}

void goYes() {
  moveBlockingTo(yesX, yesY);
}

void goNo() {
  moveBlockingTo(noX, noY);
}

void stopMotion() {
  stepperX.stop();
  stepperY.stop();
  stepperX.setSpeed(0);
  stepperY.setSpeed(0);
  Serial.println("OK STOPPING");
}

// =========================
// LIVE SWITCH MONITOR
// =========================
void monitorSwitchChanges() {
  int currentX = digitalRead(switchPinX);
  int currentY = digitalRead(switchPinY);

  if (currentX != lastSwitchStateX) {
    delay(5);
    currentX = digitalRead(switchPinX);
    if (currentX != lastSwitchStateX) {
      Serial.println(currentX == LOW ? "X_PRESSED" : "X_RELEASED");
      lastSwitchStateX = currentX;
    }
  }

  if (currentY != lastSwitchStateY) {
    delay(5);
    currentY = digitalRead(switchPinY);
    if (currentY != lastSwitchStateY) {
      Serial.println(currentY == LOW ? "Y_PRESSED" : "Y_RELEASED");
      lastSwitchStateY = currentY;
    }
  }
}

// =========================
// HOMING HELPERS
// =========================
bool confirmStablePressX() {
  if (!switchPressedX()) return false;

  unsigned long start = millis();
  while (millis() - start < stablePressMs) {
    if (!switchPressedX()) return false;
  }
  return true;
}

bool confirmStablePressY() {
  if (!switchPressedY()) return false;

  unsigned long start = millis();
  while (millis() - start < stablePressMs) {
    if (!switchPressedY()) return false;
  }
  return true;
}

float xBackedOffCoordMm() {
  if (xHomeSwitchMm < xCenterMm) return xHomeSwitchMm + homeBackoffMmX;
  else return xHomeSwitchMm - homeBackoffMmX;
}

float yBackedOffCoordMm() {
  if (yHomeSwitchMm < yCenterMm) return yHomeSwitchMm + homeBackoffMmY;
  else return yHomeSwitchMm - homeBackoffMmY;
}

bool backOffXPhysicallyUntilReleased() {
  int backoffDir = -homeDirectionX;
  long maxBackoffSteps = lround((homeBackoffMmX + 2.0) * stepsPerMmX);
  long startPos = stepperX.currentPosition();

  stepperX.setSpeed(0);
  delay(10);

  stepperX.setMaxSpeed(homeSpeedStepsX);
  stepperX.setAcceleration(1000.0);
  stepperX.setSpeed(backoffDir * homeSpeedStepsX);

  unsigned long start = millis();

  while (millis() - start < homeTimeoutMs) {
    stepperX.runSpeed();
    monitorSwitchChanges();

    if (!switchPressedX()) {
      stepperX.setSpeed(0);
      return true;
    }

    long traveled = labs(stepperX.currentPosition() - startPos);
    if (traveled >= maxBackoffSteps) break;
  }

  stepperX.setSpeed(0);
  return !switchPressedX();
}

bool backOffYPhysicallyUntilReleased() {
  long backoffSteps = lround(homeBackoffMmY * stepsPerMmY);
  long relativeSteps = -homeDirectionY * backoffSteps;

  stepperY.move(relativeSteps);

  unsigned long start = millis();
  while (stepperY.distanceToGo() != 0) {
    stepperY.run();
    monitorSwitchChanges();

    if (!switchPressedY()) return true;
    if (millis() - start > homeTimeoutMs) return false;
  }

  return !switchPressedY();
}

// =========================
// HOMING
// =========================
void homeX() {
  enableMotors();

  Serial.println("HOMING X");

  if (switchPressedX()) {
    Serial.println("X already pressed, backing off first");

    if (!backOffXPhysicallyUntilReleased()) {
      Serial.println("ERR x_switch_stuck_pressed");
      return;
    }

    stepperX.setCurrentPosition(mmToStepsX(xBackedOffCoordMm()));
  }

  stepperX.setMaxSpeed(homeSpeedStepsX);
  stepperX.setAcceleration(200.0);
  stepperX.setSpeed(homeDirectionX * homeSpeedStepsX);

  unsigned long start = millis();
  bool hit = false;

  while (millis() - start < homeTimeoutMs) {
    stepperX.runSpeed();
    monitorSwitchChanges();

    if (switchPressedX()) {
      if (confirmStablePressX()) {
        hit = true;
        break;
      }
    }
  }

  stepperX.setSpeed(0);

  if (!hit) {
    Serial.println("ERR x_home_timeout");
    applyMotionSettings();
    return;
  }

  Serial.println("X trigger confirmed");

  stepperX.setCurrentPosition(mmToStepsX(xHomeSwitchMm));

  if (!backOffXPhysicallyUntilReleased()) {
    Serial.println("ERR x_backoff_timeout_or_stuck");
    applyMotionSettings();
    return;
  }

  float xBackedOffMm = xBackedOffCoordMm();
  xBackedOffMm = clampf(xBackedOffMm, xMinMm, xMaxMm);

  stepperX.setCurrentPosition(mmToStepsX(xBackedOffMm));

  applyMotionSettings();

  stepperX.moveTo(mmToStepsX(xCenterMm));
  while (stepperX.distanceToGo() != 0) {
    stepperX.run();
    monitorSwitchChanges();
  }

  xKnown = true;

  Serial.println("OK HOMED_X_TO_CENTER");
  reportPosition();
}

void homeY() {
  enableMotors();

  Serial.println("HOMING Y");

  if (switchPressedY()) {
    Serial.println("Y already pressed, backing off first");

    if (!backOffYPhysicallyUntilReleased()) {
      Serial.println("ERR y_switch_stuck_pressed");
      return;
    }

    stepperY.setCurrentPosition(mmToStepsY(yBackedOffCoordMm()));
  }

  stepperY.setMaxSpeed(homeSpeedStepsY);
  stepperY.setAcceleration(200.0);
  stepperY.setSpeed(homeDirectionY * homeSpeedStepsY);

  unsigned long start = millis();
  bool hit = false;

  while (millis() - start < homeTimeoutMs) {
    stepperY.runSpeed();
    monitorSwitchChanges();

    if (switchPressedY()) {
      if (confirmStablePressY()) {
        hit = true;
        break;
      }
    }
  }

  stepperY.setSpeed(0);

  if (!hit) {
    Serial.println("ERR y_home_timeout");
    applyMotionSettings();
    return;
  }

  Serial.println("Y trigger confirmed");

  stepperY.setCurrentPosition(mmToStepsY(yHomeSwitchMm));

  if (!backOffYPhysicallyUntilReleased()) {
    Serial.println("ERR y_backoff_timeout_or_stuck");
    applyMotionSettings();
    return;
  }

  float yBackedOffMm = yBackedOffCoordMm();
  yBackedOffMm = clampf(yBackedOffMm, yMinMm, yMaxMm);

  stepperY.setCurrentPosition(mmToStepsY(yBackedOffMm));

  applyMotionSettings();

  stepperY.moveTo(mmToStepsY(yCenterMm));
  while (stepperY.distanceToGo() != 0) {
    stepperY.run();
    monitorSwitchChanges();
  }

  yKnown = true;

  Serial.println("OK HOMED_Y_TO_CENTER");
  reportPosition();
}

void homeAll() {
  homeY();
  homeX();

  if (xKnown && yKnown) {
    Serial.println("OK HOMEALL");
    reportPosition();
  }
}

// =========================
// SPELLING LOGIC
// =========================
bool findLetter(char c, float &x, float &y) {
  c = toupper(c);

  for (int i = 0; i < letterCount; i++) {
    if (letterMap[i].letter == c) {
      x = letterMap[i].x;
      y = letterMap[i].y;
      return true;
    }
  }

  return false;
}

bool findNumber(char c, float &x, float &y) {
  for (int i = 0; i < numberCount; i++) {
    if (numberMap[i].letter == c) {
      x = numberMap[i].x;
      y = numberMap[i].y;
      return true;
    }
  }

  return false;
}

bool numberWordToDigit(const char *word, char &digit) {
  if (strcmp(word, "ZERO") == 0) {
    digit = '0';
    return true;
  }
  if (strcmp(word, "ONE") == 0) {
    digit = '1';
    return true;
  }
  if (strcmp(word, "TWO") == 0) {
    digit = '2';
    return true;
  }
  if (strcmp(word, "THREE") == 0) {
    digit = '3';
    return true;
  }
  if (strcmp(word, "FOUR") == 0) {
    digit = '4';
    return true;
  }
  if (strcmp(word, "FIVE") == 0) {
    digit = '5';
    return true;
  }
  if (strcmp(word, "SIX") == 0) {
    digit = '6';
    return true;
  }
  if (strcmp(word, "SEVEN") == 0) {
    digit = '7';
    return true;
  }
  if (strcmp(word, "EIGHT") == 0) {
    digit = '8';
    return true;
  }
  if (strcmp(word, "NINE") == 0) {
    digit = '9';
    return true;
  }

  return false;
}

void moveNumberChar(char digit) {
  float x, y;

  if (findNumber(digit, x, y)) {
    Serial.print("NUMBER ");
    Serial.print(digit);
    Serial.print(" -> ");
    Serial.print(x, 2);
    Serial.print(" ");
    Serial.println(y, 2);

    moveBlockingTo(x, y);
  } else {
    Serial.print("SKIP UNKNOWN NUMBER ");
    Serial.println(digit);
  }
}

void moveLetterChar(char c) {
  float x, y;

  if (findLetter(c, x, y)) {
    Serial.print("LETTER ");
    Serial.print(c);
    Serial.print(" -> ");
    Serial.print(x, 2);
    Serial.print(" ");
    Serial.println(y, 2);

    moveBlockingTo(x, y);
  } else {
    Serial.print("SKIP UNKNOWN CHAR ");
    Serial.println(c);
  }
}

void spellToken(char *token) {
  if (token[0] == '\0') return;

  char digit;

  // If token is ONE, TWO, THREE, etc., go to number position
  if (numberWordToDigit(token, digit)) {
    moveNumberChar(digit);
    return;
  }

  // Otherwise process character by character
  for (int i = 0; token[i] != '\0'; i++) {
    char c = token[i];

    if (c >= '0' && c <= '9') {
      moveNumberChar(c);
    } else if (c >= 'A' && c <= 'Z') {
      moveLetterChar(c);
    } else {
      Serial.print("SKIP UNKNOWN CHAR ");
      Serial.println(c);
    }
  }
}

void spellWord(char *word) {
  if (!fullPositionKnown()) {
    Serial.println("ERR position_unknown_use_HOMEALL_or_ZEROALL");
    return;
  }

  // Clean full input for YES/NO special case
  char cleanWord[50];
  int j = 0;

  for (int i = 0; word[i] != '\0' && j < 49; i++) {
    char c = word[i];

    if (isAlphaNumeric(c)) {
      cleanWord[j++] = toupper(c);
    }
  }

  cleanWord[j] = '\0';

  // Special whole-word targets
  if (strcmp(cleanWord, "YES") == 0) {
    Serial.println("SPECIAL WORD YES");
    goYes();
    Serial.println("OK SPELL_DONE");
    return;
  }

  if (strcmp(cleanWord, "NO") == 0) {
    Serial.println("SPECIAL WORD NO");
    goNo();
    Serial.println("OK SPELL_DONE");
    return;
  }

  Serial.print("SPELLING ");
  Serial.println(cleanWord);

  // Tokenize input so SPELL ONE goes to 1, not O-N-E
  char token[20];
  int tokenIndex = 0;

  for (int i = 0; ; i++) {
    char c = word[i];

    if (isAlphaNumeric(c)) {
      if (tokenIndex < 19) {
        token[tokenIndex++] = toupper(c);
      }
    } else {
      if (tokenIndex > 0) {
        token[tokenIndex] = '\0';
        spellToken(token);
        tokenIndex = 0;
      }

      if (c == '\0') break;
    }
  }

  Serial.println("OK SPELL_DONE");
}

// =========================
// AUTO STARTUP
// =========================
void autoHomeOnStartup() {
  delay(1000);
  Serial.println("AUTO HOMEALL START");
  homeAll();

  if (fullPositionKnown()) {
    Serial.println("AUTO MOVE TO REST CENTER");
    goCenter();
    Serial.println("READY_AT_CENTER");
  } else {
    Serial.println("ERR AUTO_HOME_FAILED");
  }
}

// =========================
// COMMAND PARSER
// =========================
void parseCommand(char *line) {
  while (*line == ' ' || *line == '\t') line++;

  int len = strlen(line);
  while (len > 0 && (line[len - 1] == ' ' || line[len - 1] == '\t')) {
    line[len - 1] = '\0';
    len--;
  }

  Serial.print("RAW:[");
  Serial.print(line);
  Serial.println("]");

  if (strcmp(line, "WHERE") == 0) {
    reportPosition();
    return;
  }

  if (strcmp(line, "SWITCHES") == 0) {
    reportSwitches();
    return;
  }

  if (strcmp(line, "ZEROALL") == 0) {
    zeroAllHere();
    return;
  }

  if (strcmp(line, "ZEROX") == 0) {
    zeroXHere();
    return;
  }

  if (strcmp(line, "ZEROY") == 0) {
    zeroYHere();
    return;
  }

  if (strcmp(line, "HOMEX") == 0) {
    homeX();
    return;
  }

  if (strcmp(line, "HOMEY") == 0) {
    homeY();
    return;
  }

  if (strcmp(line, "HOMEALL") == 0) {
    homeAll();
    return;
  }

  if (strcmp(line, "YES") == 0 || strcmp(line, "GOTOYES") == 0) {
    goYes();
    return;
  }

  if (strcmp(line, "NO") == 0 || strcmp(line, "GOTONO") == 0) {
    goNo();
    return;
  }

  if (strncmp(line, "SPELL ", 6) == 0) {
    spellWord(line + 6);
    return;
  }

  if (strcmp(line, "CENTER") == 0) {
    goCenter();
    return;
  }

  if (strcmp(line, "STOP") == 0) {
    stopMotion();
    return;
  }

  if (strcmp(line, "ENABLE") == 0) {
    enableMotors();
    Serial.println("OK ENABLED");
    return;
  }

  if (strcmp(line, "DISABLE") == 0) {
    disableMotors();
    Serial.println("OK DISABLED");
    return;
  }

  char cmd[20];
  long x, y;

  int matched = sscanf(line, "%19s %ld %ld", cmd, &x, &y);

  if (matched == 3 && strcmp(cmd, "GOTO") == 0) {
    goToMm((float)x, (float)y);
    return;
  }

  if (matched == 3 && strcmp(cmd, "OFFSET") == 0) {
    if (!fullPositionKnown()) {
      Serial.println("ERR position_unknown_use_HOMEALL_or_ZEROALL");
      return;
    }

    float newX = currentXmm() + (float)x;
    float newY = currentYmm() + (float)y;
    goToMm(newX, newY);
    return;
  }

  Serial.println("ERR unknown_command");
}

// =========================
// SERIAL READER
// =========================
void readSerialLine() {
  while (Serial.available() > 0) {
    char c = Serial.read();

    if (c == '\r') continue;

    if (c == '\n') {
      inputBuffer[inputIndex] = '\0';
      parseCommand(inputBuffer);
      inputIndex = 0;
      return;
    }

    if (inputIndex < sizeof(inputBuffer) - 1) {
      inputBuffer[inputIndex++] = c;
    } else {
      inputIndex = 0;
      Serial.println("ERR line_too_long");
    }
  }
}

// =========================
// SETUP / LOOP
// =========================
void setup() {
  Serial.begin(115200);

  if (USE_ENABLE_PIN) {
    pinMode(ENABLE_PIN, OUTPUT);
  }

  pinMode(switchPinX, INPUT_PULLUP);
  pinMode(switchPinY, INPUT_PULLUP);

  enableMotors();
  applyMotionSettings();

  lastSwitchStateX = digitalRead(switchPinX);
  lastSwitchStateY = digitalRead(switchPinY);

  Serial.println("READY");
  Serial.println("COMMANDS: WHERE, SWITCHES, HOMEX, HOMEY, HOMEALL, YES, NO, SPELL word, CENTER, GOTO x y, OFFSET dx dy");

  autoHomeOnStartup();
}

void loop() {
  readSerialLine();
  monitorSwitchChanges();

  stepperX.run();
  stepperY.run();
}