import json
import random
import time

from locust_plugins.users.socketio import SocketIOUser

# no idea why mypy is complaining about this:
from locust import between, task  # type: ignore


class RubinTVWebsocketTester(SocketIOUser):
    wait_time = between(1, 3)  # Optional: Adjust the wait time between tasks

    def on_start(self) -> None:
        """Initialize any necessary variables here"""
        self.client_id: None | str = None

    @task
    def my_task(self) -> None:
        local_url = "ws://localhost:8000/rubintv/ws/"

        self.connect(local_url)

        # Wait until the client_id is received
        while not self.client_id:
            time.sleep(0.1)

        print(f"Connected with client ID #{self.client_id}")

        # Randomly decide whether to disconnect
        if random.random() < 0.2:  # 20% chance to disconnect unexpectedly
            print("Closing connection unexpectedly...")
            self.stop(force=True)
            return  # Stop execution of this task

        # Otherwise, continue with normal operation
        message = json.dumps(
            {
                "clientID": self.client_id,
                "messageType": "service",
                "message": "camera base-usdf/fake_auxtel",
            }
        )
        print(f"Sending message: {message}")
        self.send(body=message, name="send_service_request")

    def on_message(self, message: str) -> None:
        print(f"Received message: {message}")
        if not self.client_id:
            self.client_id = message  # Assume the message is the client ID

    def on_stop(self) -> None:
        """Disconnect cleanly if not already disconnected"""
        if self.client_id:
            self.stop()
