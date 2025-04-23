import sys
import speech_recognition as sr
import time
import socket
import threading
import struct
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QTextEdit, QLabel, 
                            QComboBox, QSlider, QGroupBox, QCheckBox, QSpinBox)
from PyQt5.QtCore import Qt, pyqtSignal, QThread

class UARTFormatSettings:
    """Class to store UART format settings"""
    def __init__(self):
        self.data_bits = 8
        self.parity = 'N'  # N=None, E=Even, O=Odd
        self.stop_bits = 1
        self.baud_rate = 9600
        self.add_cr = False
        self.add_lf = True
        self.hex_output = False
        
    def format_message(self, message):
        """Format the message according to UART settings"""
        if self.add_cr and self.add_lf:
            message = message + "\r\n"
        elif self.add_cr:
            message = message + "\r"
        elif self.add_lf:
            message = message + "\n"
            
        # Convert to bytes if not already
        if isinstance(message, str):
            message = message.encode('utf-8')
            
        if self.hex_output:
            # Format as hex bytes
            return bytes.fromhex(message.hex())
        
        return message

class SpeechRecognitionThread(QThread):
    text_recognized = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, socket_conn, recognizer, uart_settings, energy_threshold=300):
        super().__init__()
        self.socket_conn = socket_conn
        self.recognizer = recognizer
        self.recognizer.energy_threshold = energy_threshold
        self.uart_settings = uart_settings
        self.running = True
        self.paused = False
    
    def run(self):
        while self.running:
            if not self.paused:
                try:
                    with sr.Microphone() as source:
                        # adjust for ambient noise
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                        try:
                            audio_text = self.recognizer.listen(source, timeout=None, phrase_time_limit=10)
                            try:
                                text = self.recognizer.recognize_google(audio_text)
                                self.text_recognized.emit(text)
                                
                                # Format and send message in UART format
                                uart_formatted = self.uart_settings.format_message(text)
                                self.socket_conn.sendall(uart_formatted)
                                
                            except sr.UnknownValueError:
                                pass
                            except sr.RequestError as e:
                                self.error_occurred.emit(f"Google Speech Recognition service error: {e}")
                        except sr.WaitTimeoutError:
                            pass
                except Exception as e:
                    self.error_occurred.emit(f"Error in speech recognition: {e}")
            time.sleep(0.1)
    
    def stop(self):
        self.running = False
        self.wait()
    
    def pause(self):
        self.paused = True
    
    def resume(self):
        self.paused = False
    
    def set_energy_threshold(self, value):
        self.recognizer.energy_threshold = value


class ServerConnectionThread(QThread):
    connection_success = pyqtSignal()
    connection_error = pyqtSignal(str)
    server_message = pyqtSignal(str)
    
    def __init__(self, host, port, uart_settings):
        super().__init__()
        self.host = host
        self.port = port
        self.uart_settings = uart_settings
        self.socket = None
        self.connected = False
    
    def run(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            self.connection_success.emit()
            
            # Listen for messages from server
            while self.connected:
                try:
                    data = self.socket.recv(1024)
                    if data:
                        try:
                            message = data.decode('utf-8')
                        except UnicodeDecodeError:
                            message = f"Binary data: {data.hex()}"
                        self.server_message.emit(message)
                except:
                    break
                
        except socket.error as e:
            self.connected = False
            self.connection_error.emit(f"Socket error: {e}")
    
    def send_message(self, message):
        if self.connected and self.socket:
            try:
                uart_formatted = self.uart_settings.format_message(message)
                self.socket.sendall(uart_formatted)
                return True
            except Exception as e:
                self.connection_error.emit(f"Failed to send message: {e}")
                return False
        return False
    
    def disconnect(self):
        self.connected = False
        if self.socket:
            self.socket.close()


class SpeechRecognitionGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CyTTY - PuTTY but for CyBOT")
        self.setGeometry(100, 100, 900, 700)
        
        # Initialize variables
        self.r = sr.Recognizer()
        self.r.energy_threshold = 300
        self.host = "192.168.1.1"
        self.port = 288
        self.server_thread = None
        self.speech_thread = None
        self.uart_settings = UARTFormatSettings()
        
        # Set up the UI
        self.init_ui()
        self.populate_microphones()
        
    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Connection settings
        connection_group = QGroupBox("Server Connection")
        connection_layout = QHBoxLayout()
        
        self.host_label = QLabel("Host:")
        self.host_input = QTextEdit()
        self.host_input.setText(self.host)
        self.host_input.setMaximumHeight(30)
        
        self.port_label = QLabel("Port:")
        self.port_input = QTextEdit()
        self.port_input.setText(str(self.port))
        self.port_input.setMaximumHeight(30)
        
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_to_server)
        
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.disconnect_from_server)
        self.disconnect_button.setEnabled(False)
        
        connection_layout.addWidget(self.host_label)
        connection_layout.addWidget(self.host_input)
        connection_layout.addWidget(self.port_label)
        connection_layout.addWidget(self.port_input)
        connection_layout.addWidget(self.connect_button)
        connection_layout.addWidget(self.disconnect_button)
        connection_group.setLayout(connection_layout)
        
        # UART settings
        uart_group = QGroupBox("UART Settings")
        uart_layout = QVBoxLayout()
        
        uart_row1 = QHBoxLayout()
        
        self.baud_label = QLabel("Baud Rate:")
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"])
        self.baud_combo.setCurrentText("9600")
        self.baud_combo.currentTextChanged.connect(self.update_uart_settings)
        
        self.data_bits_label = QLabel("Data Bits:")
        self.data_bits_combo = QComboBox()
        self.data_bits_combo.addItems(["5", "6", "7", "8"])
        self.data_bits_combo.setCurrentText("8")
        self.data_bits_combo.currentTextChanged.connect(self.update_uart_settings)
        
        self.parity_label = QLabel("Parity:")
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(["None", "Even", "Odd"])
        self.parity_combo.currentTextChanged.connect(self.update_uart_settings)
        
        self.stop_bits_label = QLabel("Stop Bits:")
        self.stop_bits_combo = QComboBox()
        self.stop_bits_combo.addItems(["1", "1.5", "2"])
        self.stop_bits_combo.currentTextChanged.connect(self.update_uart_settings)
        
        uart_row1.addWidget(self.baud_label)
        uart_row1.addWidget(self.baud_combo)
        uart_row1.addWidget(self.data_bits_label)
        uart_row1.addWidget(self.data_bits_combo)
        uart_row1.addWidget(self.parity_label)
        uart_row1.addWidget(self.parity_combo)
        uart_row1.addWidget(self.stop_bits_label)
        uart_row1.addWidget(self.stop_bits_combo)
        
        uart_row2 = QHBoxLayout()
        
        self.cr_checkbox = QCheckBox("Add CR (\\r)")
        self.cr_checkbox.setChecked(self.uart_settings.add_cr)
        self.cr_checkbox.stateChanged.connect(self.update_uart_settings)
        
        self.lf_checkbox = QCheckBox("Add LF (\\n)")
        self.lf_checkbox.setChecked(self.uart_settings.add_lf)
        self.lf_checkbox.stateChanged.connect(self.update_uart_settings)
        
        self.hex_checkbox = QCheckBox("Hex Output")
        self.hex_checkbox.setChecked(self.uart_settings.hex_output)
        self.hex_checkbox.stateChanged.connect(self.update_uart_settings)
        
        uart_row2.addWidget(self.cr_checkbox)
        uart_row2.addWidget(self.lf_checkbox)
        uart_row2.addWidget(self.hex_checkbox)
        uart_row2.addStretch()
        
        uart_layout.addLayout(uart_row1)
        uart_layout.addLayout(uart_row2)
        uart_group.setLayout(uart_layout)
        
        # Microphone settings
        mic_group = QGroupBox("Microphone Settings")
        mic_layout = QHBoxLayout()
        
        self.mic_label = QLabel("Microphone:")
        self.mic_combo = QComboBox()
        
        self.threshold_label = QLabel("Energy Threshold:")
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setMinimum(100)
        self.threshold_slider.setMaximum(4000)
        self.threshold_slider.setValue(300)
        self.threshold_slider.setTickInterval(100)
        self.threshold_slider.setTickPosition(QSlider.TicksBelow)
        self.threshold_slider.valueChanged.connect(self.update_threshold)
        
        self.threshold_value = QLabel("300")
        
        mic_layout.addWidget(self.mic_label)
        mic_layout.addWidget(self.mic_combo)
        mic_layout.addWidget(self.threshold_label)
        mic_layout.addWidget(self.threshold_slider)
        mic_layout.addWidget(self.threshold_value)
        mic_group.setLayout(mic_layout)
        
        # Speech recognition controls
        control_group = QGroupBox("Controls")
        control_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start Listening")
        self.start_button.clicked.connect(self.start_speech_recognition)
        self.start_button.setEnabled(False)
        
        self.stop_button = QPushButton("Stop Listening")
        self.stop_button.clicked.connect(self.stop_speech_recognition)
        self.stop_button.setEnabled(False)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.pause_speech_recognition)
        self.pause_button.setEnabled(False)
        
        self.resume_button = QPushButton("Resume")
        self.resume_button.clicked.connect(self.resume_speech_recognition)
        self.resume_button.setEnabled(False)
        
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.pause_button)
        control_layout.addWidget(self.resume_button)
        control_group.setLayout(control_layout)
        
        # Text input
        input_group = QGroupBox("Manual Text Input")
        input_layout = QHBoxLayout()
        
        self.text_input = QTextEdit()
        self.text_input.setMaximumHeight(60)
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_text)
        self.send_button.setEnabled(False)
        
        self.send_hex_button = QPushButton("Send Hex")
        self.send_hex_button.clicked.connect(self.send_hex)
        self.send_hex_button.setEnabled(False)
        
        input_layout.addWidget(self.text_input)
        input_layout.addWidget(self.send_button)
        input_layout.addWidget(self.send_hex_button)
        input_group.setLayout(input_layout)
        
        # Log area
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        
        log_buttons_layout = QHBoxLayout()
        
        self.clear_log_button = QPushButton("Clear Log")
        self.clear_log_button.clicked.connect(self.clear_log)
        
        self.show_hex_checkbox = QCheckBox("Show Hex in Log")
        self.show_hex_checkbox.setChecked(False)
        
        log_buttons_layout.addWidget(self.clear_log_button)
        log_buttons_layout.addWidget(self.show_hex_checkbox)
        log_buttons_layout.addStretch()
        
        log_layout.addWidget(self.log_text)
        log_layout.addLayout(log_buttons_layout)
        log_group.setLayout(log_layout)
        
        # Add all components to main layout
        main_layout.addWidget(connection_group)
        main_layout.addWidget(uart_group)
        main_layout.addWidget(mic_group)
        main_layout.addWidget(control_group)
        main_layout.addWidget(input_group)
        main_layout.addWidget(log_group)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # Initial log message
        self.log("UART Speech Recognition GUI started. Please connect to server.")
    
    def populate_microphones(self):
        try:
            mic_list = sr.Microphone.list_microphone_names()
            self.mic_combo.addItems(mic_list)
            if len(mic_list) > 1:
                self.mic_combo.setCurrentIndex(1)  # Default to second mic as in original code
            self.log(f"Found {len(mic_list)} microphones")
        except Exception as e:
            self.log(f"Error getting microphones: {e}")
    
    def update_threshold(self, value):
        self.threshold_value.setText(str(value))
        self.r.energy_threshold = value
        if self.speech_thread and self.speech_thread.isRunning():
            self.speech_thread.set_energy_threshold(value)
    
    def update_uart_settings(self):
        self.uart_settings.baud_rate = int(self.baud_combo.currentText())
        self.uart_settings.data_bits = int(self.data_bits_combo.currentText())
        
        parity_text = self.parity_combo.currentText()
        if parity_text == "None":
            self.uart_settings.parity = 'N'
        elif parity_text == "Even":
            self.uart_settings.parity = 'E'
        elif parity_text == "Odd":
            self.uart_settings.parity = 'O'
        
        stop_bits_text = self.stop_bits_combo.currentText()
        if stop_bits_text == "1":
            self.uart_settings.stop_bits = 1
        elif stop_bits_text == "1.5":
            self.uart_settings.stop_bits = 1.5
        elif stop_bits_text == "2":
            self.uart_settings.stop_bits = 2
        
        self.uart_settings.add_cr = self.cr_checkbox.isChecked()
        self.uart_settings.add_lf = self.lf_checkbox.isChecked()
        self.uart_settings.hex_output = self.hex_checkbox.isChecked()
        
        self.log(f"UART settings updated: {self.uart_settings.baud_rate} baud, {self.uart_settings.data_bits} bits, "
               f"Parity: {self.uart_settings.parity}, Stop bits: {self.uart_settings.stop_bits}")
    
    def connect_to_server(self):
        try:
            self.host = self.host_input.toPlainText().strip()
            self.port = int(self.port_input.toPlainText().strip())
            
            self.log(f"Connecting to {self.host}:{self.port}...")
            self.server_thread = ServerConnectionThread(self.host, self.port, self.uart_settings)
            self.server_thread.connection_success.connect(self.on_connection_success)
            self.server_thread.connection_error.connect(self.log)
            self.server_thread.server_message.connect(self.on_server_message)
            self.server_thread.start()
        except ValueError:
            self.log("Invalid port number")
        except Exception as e:
            self.log(f"Error: {e}")
    
    def disconnect_from_server(self):
        if self.speech_thread and self.speech_thread.isRunning():
            self.stop_speech_recognition()
        
        if self.server_thread:
            self.server_thread.disconnect()
            self.server_thread.wait()
            self.server_thread = None
        
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.send_button.setEnabled(False)
        self.send_hex_button.setEnabled(False)
        self.log("Disconnected from server")
    
    def on_connection_success(self):
        self.log(f"Connected to {self.host}:{self.port}")
        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)
        self.start_button.setEnabled(True)
        self.send_button.setEnabled(True)
        self.send_hex_button.setEnabled(True)
    
    def on_server_message(self, message):
        if self.show_hex_checkbox.isChecked() and isinstance(message, str):
            hex_repr = ' '.join(f'{ord(c):02x}' for c in message)
            self.log(f"Server: {message} [Hex: {hex_repr}]")
        else:
            self.log(f"Server: {message}")
    
    def start_speech_recognition(self):
        if not self.server_thread or not self.server_thread.connected:
            self.log("Not connected to server")
            return
        
        try:
            # Initialize speech recognition thread
            self.speech_thread = SpeechRecognitionThread(
                self.server_thread.socket, 
                self.r,
                self.uart_settings,
                energy_threshold=self.threshold_slider.value()
            )
            self.speech_thread.text_recognized.connect(self.on_speech_recognized)
            self.speech_thread.error_occurred.connect(self.log)
            self.speech_thread.start()
            
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.pause_button.setEnabled(True)
            self.resume_button.setEnabled(False)
            
            self.log("Speech recognition started")
        except Exception as e:
            self.log(f"Error starting speech recognition: {e}")
    
    def stop_speech_recognition(self):
        if self.speech_thread and self.speech_thread.isRunning():
            self.speech_thread.stop()
            self.speech_thread = None
            
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(False)
        
        self.log("Speech recognition stopped")
    
    def pause_speech_recognition(self):
        if self.speech_thread and self.speech_thread.isRunning():
            self.speech_thread.pause()
            self.pause_button.setEnabled(False)
            self.resume_button.setEnabled(True)
            self.log("Speech recognition paused")
    
    def resume_speech_recognition(self):
        if self.speech_thread and self.speech_thread.isRunning():
            self.speech_thread.resume()
            self.pause_button.setEnabled(True)
            self.resume_button.setEnabled(False)
            self.log("Speech recognition resumed")
    
    def on_speech_recognized(self, text):
        if self.show_hex_checkbox.isChecked():
            formatted_text = self.uart_settings.format_message(text)
            if isinstance(formatted_text, bytes):
                hex_repr = ' '.join(f'{b:02x}' for b in formatted_text)
                self.log(f"You said: {text} [Hex: {hex_repr}]")
            else:
                self.log(f"You said: {text}")
        else:
            self.log(f"You said: {text}")
    
    def send_text(self):
        if not self.server_thread or not self.server_thread.connected:
            self.log("Not connected to server")
            return
        
        text = self.text_input.toPlainText().strip()
        if text:
            success = self.server_thread.send_message(text)
            if success:
                formatted_text = self.uart_settings.format_message(text)
                if self.show_hex_checkbox.isChecked() and isinstance(formatted_text, bytes):
                    hex_repr = ' '.join(f'{b:02x}' for b in formatted_text)
                    self.log(f"Sent: {text} [Hex: {hex_repr}]")
                else:
                    self.log(f"Sent: {text}")
                self.text_input.clear()
            else:
                self.log("Failed to send message")
    
    def send_hex(self):
        if not self.server_thread or not self.server_thread.connected:
            self.log("Not connected to server")
            return
        
        hex_text = self.text_input.toPlainText().strip()
        if hex_text:
            try:
                # Convert hex string to bytes
                hex_text = hex_text.replace(' ', '')  # Remove spaces
                byte_data = bytes.fromhex(hex_text)
                
                self.server_thread.socket.sendall(byte_data)
                self.log(f"Sent hex: {' '.join(f'{b:02x}' for b in byte_data)}")
                self.text_input.clear()
            except ValueError:
                self.log("Invalid hex format. Use format like 'AB CD EF' or 'ABCDEF'")
    
    def log(self, message):
        self.log_text.append(f"{message}")
    
    def clear_log(self):
        self.log_text.clear()
    
    def closeEvent(self, event):
        if self.speech_thread and self.speech_thread.isRunning():
            self.speech_thread.stop()
        
        if self.server_thread:
            self.server_thread.disconnect()
            self.server_thread.wait()
        
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SpeechRecognitionGUI()
    window.show()
    sys.exit(app.exec_())