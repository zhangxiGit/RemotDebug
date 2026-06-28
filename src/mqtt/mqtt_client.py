import time
import random
import string
from typing import Callable, Optional
import paho.mqtt.client as mqtt
from config.config import MQTTConfig

class MQTTClient:
    def __init__(self, config: MQTTConfig):
        self.config = config
        self.client = None
        self.connected = False
        self.on_message_callback: Optional[Callable[[str, bytes], None]] = None
        self.on_connect_callback: Optional[Callable[[bool], None]] = None
        self.client_id = self._generate_client_id()
        self._intentional_disconnect = False  # 是否为用户主动断开
        self.subscribed_topics = set()  # 已订阅的Topic集合，用于重连后重新订阅
    
    def _generate_client_id(self) -> str:
        if self.config.client_id:
            return self.config.client_id
        suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        return f"{self.config.client_id_prefix}{suffix}"
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            # 重连后自动重新订阅之前的Topic
            if self.subscribed_topics:
                for topic in self.subscribed_topics:
                    self.client.subscribe(topic)
            if self.on_connect_callback:
                self.on_connect_callback(True)
        else:
            self.connected = False
            if self.on_connect_callback:
                self.on_connect_callback(False)
    
    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        # 不再调用 on_connect_callback(False)，避免与初始连接失败混淆
        # paho-mqtt 的 loop_start() 配合 reconnect_delay_set 会自动重连
        # 手动 reconnect() 会与自动重连机制冲突，导致反复断连
    
    def _on_message(self, client, userdata, msg):
        if self.on_message_callback:
            self.on_message_callback(msg.topic, msg.payload)
    
    def connect(self) -> bool:
        try:
            self.client = mqtt.Client(client_id=self.client_id, clean_session=True)
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            if self.config.username and self.config.password:
                self.client.username_pw_set(self.config.username, self.config.password)

            # 设置自动重连的延迟参数（最小1秒，最大30秒）
            self.client.reconnect_delay_set(min_delay=1, max_delay=30)

            self.client.connect(self.config.broker, self.config.port, self.config.keepalive)
            self.client.loop_start()
            
            timeout = 5
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            return self.connected
        except Exception as e:
            if self.on_connect_callback:
                self.on_connect_callback(False)
            return False
    
    def disconnect(self):
        if self.client:
            self._intentional_disconnect = True  # 标记为用户主动断开
            self.subscribed_topics.clear()  # 清空已订阅的Topic集合
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
    
    def publish(self, topic: str, payload: bytes, qos: int = 0) -> bool:
        if not self.connected or not self.client:
            return False
        
        try:
            result = self.client.publish(topic, payload, qos)
            result.wait_for_publish(timeout=5)
            return result.is_published()
        except Exception:
            return False
    
    def subscribe(self, topic: str, qos: int = 0) -> bool:
        if not self.connected or not self.client:
            return False
        
        try:
            self.client.subscribe(topic, qos)
            self.subscribed_topics.add(topic)  # 记录已订阅的Topic
            return True
        except Exception:
            return False

    def unsubscribe(self, topic: str) -> bool:
        if not self.connected or not self.client:
            return False
        
        try:
            self.client.unsubscribe(topic)
            self.subscribed_topics.discard(topic)  # 从已订阅集合中移除
            return True
        except Exception:
            return False
