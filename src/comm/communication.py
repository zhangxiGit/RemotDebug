from abc import ABC, abstractmethod
from typing import Optional, Callable
import serial
import serial.tools.list_ports

class CommunicationInterface(ABC):
    @abstractmethod
    def connect(self) -> bool:
        pass
    
    @abstractmethod
    def disconnect(self):
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        pass
    
    @abstractmethod
    def send(self, data: bytes) -> int:
        pass
    
    @abstractmethod
    def receive(self, size: int = 1024) -> Optional[bytes]:
        pass
    
    def set_receive_callback(self, callback: Callable[[bytes], None]):
        self.receive_callback = callback

class SerialInterface(CommunicationInterface):
    def __init__(self, port: str, baud_rate: int = 115200,
                 data_bits: int = 8, parity: str = 'N', stop_bits: int = 1, timeout: float = 0.05):
        self.port = port
        self.baud_rate = baud_rate
        self.data_bits = data_bits
        self.parity = parity
        self.stop_bits = stop_bits
        self.timeout = timeout
        self.serial_port = None
        self.receive_callback: Optional[Callable[[bytes], None]] = None
    
    def connect(self) -> bool:
        try:
            self.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                bytesize=self.data_bits,
                parity=self.parity,
                stopbits=self.stop_bits,
                timeout=self.timeout
            )
            return True
        except Exception:
            return False
    
    def disconnect(self):
        if self.serial_port:
            self.serial_port.close()
            self.serial_port = None
    
    def is_connected(self) -> bool:
        return self.serial_port is not None and self.serial_port.is_open
    
    def send(self, data: bytes) -> int:
        if not self.is_connected():
            return 0
        
        try:
            return self.serial_port.write(data)
        except Exception:
            return 0
    
    def receive(self, size: int = 1024) -> Optional[bytes]:
        if not self.is_connected():
            return None
        
        try:
            data = self.serial_port.read(size)
            if data and self.receive_callback:
                self.receive_callback(data)
            return data
        except Exception:
            return None
    
    @staticmethod
    def list_ports() -> list:
        ports = []
        try:
            for port in serial.tools.list_ports.comports():
                ports.append({
                    'port': port.device,
                    'description': port.description,
                    'hwid': port.hwid
                })
        except Exception:
            pass
        return ports

class HIDInterface(CommunicationInterface):
    def __init__(self, vendor_id: int, product_id: int, usage_page: int = 0xFF00, usage: int = 0x0001):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.usage_page = usage_page
        self.usage = usage
        self.hid_device = None
        self.receive_callback: Optional[Callable[[bytes], None]] = None
    
    def connect(self) -> bool:
        try:
            import hid
            self.hid_device = hid.device()
            self.hid_device.open(self.vendor_id, self.product_id)
            return True
        except Exception:
            return False
    
    def disconnect(self):
        if self.hid_device:
            self.hid_device.close()
            self.hid_device = None
    
    def is_connected(self) -> bool:
        return self.hid_device is not None
    
    def send(self, data: bytes) -> int:
        if not self.is_connected():
            return 0
        
        try:
            report_data = bytes([0x00]) + data
            return self.hid_device.write(report_data)
        except Exception:
            return 0
    
    def receive(self, size: int = 64) -> Optional[bytes]:
        if not self.is_connected():
            return None
        
        try:
            data = self.hid_device.read(size)
            if data and self.receive_callback:
                self.receive_callback(bytes(data[1:]))
            return bytes(data[1:]) if len(data) > 1 else bytes(data)
        except Exception:
            return None
    
    @staticmethod
    def list_devices() -> list:
        devices = []
        try:
            import hid
            for device in hid.enumerate():
                devices.append({
                    'vendor_id': device['vendor_id'],
                    'product_id': device['product_id'],
                    'product_string': device.get('product_string', ''),
                    'manufacturer_string': device.get('manufacturer_string', '')
                })
        except Exception:
            pass
        return devices
