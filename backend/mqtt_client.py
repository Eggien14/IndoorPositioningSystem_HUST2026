"""
MQTT Client for receiving sensor data in real-time
"""
import paho.mqtt.client as mqtt
from typing import Callable, Optional, Dict, List
import os
from dotenv import load_dotenv

load_dotenv()

# MQTT Configuration
# MQTT_BROKER = '192.168.0.102'
MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_KEEPALIVE = int(os.getenv('MQTT_KEEPALIVE', 60))


class MQTTClient:
    """MQTT Client wrapper for handling sensor data collection"""
    
    def __init__(self):
        self.client: Optional[mqtt.Client] = None
        self.is_connected = False
        self.current_topic: Optional[str] = None
        self.message_callback: Optional[Callable] = None
        self.topic_callbacks: Dict[str, List[Callable[[str], None]]] = {}
        
    def connect(self) -> bool:
        """Connect to MQTT broker"""
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            self.client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
            self.client.loop_start()
            
            print(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            return True
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.is_connected = False
            print("Disconnected from MQTT broker")

    def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False) -> bool:
        """Publish a message to a topic. Returns True on success."""
        if not self.client or not self.is_connected:
            print(f"Cannot publish to {topic}: not connected to MQTT broker")
            return False
        try:
            result = self.client.publish(topic, payload, qos=qos, retain=retain)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            print(f"Error publishing to {topic}: {e}")
            return False

    def subscribe(self, topic: str, callback: Callable):
        """
        Subscribe to a topic with a callback function
        
        Args:
            topic: MQTT topic to subscribe to
            callback: Function to call when message received (receives message payload as string)
        """
        if not self.client:
            self.connect()
        if topic not in self.topic_callbacks:
            self.topic_callbacks[topic] = []
            self.client.subscribe(topic)
            print(f"Subscribed to topic: {topic}")

        self.topic_callbacks[topic].append(callback)
        self.current_topic = topic
        self.message_callback = callback
    
    def unsubscribe(self, topic: Optional[str] = None, callback: Optional[Callable] = None):
        """Unsubscribe callback/topic. If topic is None, remove all subscriptions."""
        if not self.client:
            return

        if topic is None:
            for existing_topic in list(self.topic_callbacks.keys()):
                self.client.unsubscribe(existing_topic)
                print(f"Unsubscribed from topic: {existing_topic}")
            self.topic_callbacks.clear()
            self.current_topic = None
            self.message_callback = None
            return

        callbacks = self.topic_callbacks.get(topic, [])
        if callback and callbacks:
            callbacks = [cb for cb in callbacks if cb != callback]

        if callback is None or not callbacks:
            self.client.unsubscribe(topic)
            self.topic_callbacks.pop(topic, None)
            print(f"Unsubscribed from topic: {topic}")
        else:
            self.topic_callbacks[topic] = callbacks

        if self.current_topic == topic:
            self.current_topic = None
            self.message_callback = None
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker"""
        if rc == 0:
            self.is_connected = True
            print("MQTT connection established")
        else:
            print(f"MQTT connection failed with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker"""
        self.is_connected = False
        if rc != 0:
            print(f"Unexpected MQTT disconnection (code {rc})")
    
    def _on_message(self, client, userdata, msg):
        """Callback when message received"""
        try:
            payload = msg.payload.decode('utf-8')
            topic = msg.topic
            for sub_topic, callbacks in self.topic_callbacks.items():
                if mqtt.topic_matches_sub(sub_topic, topic):
                    for callback in callbacks:
                        callback(payload)
        except Exception as e:
            print(f"Error processing MQTT message: {e}")


# Global MQTT client instance
mqtt_client = MQTTClient()
