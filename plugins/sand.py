from wrappers import plugin, onMqtt, regex, service
from main import ERM
import json
import hbmqtt.session
from collections import deque
from hbmqtt.mqtt.constants import QOS_2
import asyncio

@plugin
class sandy:

    def __init__(self, e: ERM):
        self.e = e
        self.current_state = [deque(maxlen=1) for i in range(4)]
        self.targets = [30, 90, 150, 210]
        self.triggered = [False, False, False, False]
        self.final = False
        self.tolerance = 20
        self.ez = False
        self.address = 30

    @onMqtt("sand")
    async def sandfoo(self, message: hbmqtt.session.ApplicationMessage):
        if len(json.loads(message.publish_packet.payload.data.decode()[:-1])["devices"]) == 0:
            return
        self.address = json.loads(message.publish_packet.payload.data.decode()[:-1])["devices"][0]["address"]
        data = json.loads(message.publish_packet.payload.data.decode()[:-1])["devices"][0]["data"][:4]
        new = False
        for i, x in enumerate(data):
            self.current_state[i].append(x)
            if all([abs(self.targets[i]-xx) < self.tolerance for xx in (self.current_state[i])]):
                if not self.triggered[i]:
                    print(f"target reached for {i}")
                    new = True
                    self.triggered[i] = True
            elif not self.ez:
                self.triggered[i] = False
        if self.ez and new:
            dat = [1 if t else 0 for t in self.triggered] + [self.targets[i] if x else 0 for i, x in
                                                           enumerate(self.triggered)]
            dat2 = {self.address:dat}

            await self.e.MQTT.publish('game/sand/control',
            json.dumps(dat2).encode(), qos=QOS_2,
                                      retain=True)

        if all(self.triggered) and not self.final:#
            self.final = True
            print("all triggered")
            dat = [1, 1, 1, 1] + self.targets
            dat2 = {self.address: dat}
            await self.e.MQTT.publish('game/sand/control',
                                      json.dumps(dat2).encode(), qos=QOS_2,
                                      retain=True)


    @onMqtt("sand/ez")
    async def sandezon(self, message):
        if message.publish_packet.payload.data.decode() == "on":
            print("ez mode activated")
            self.ez = True
        else:
            print("ez mode off")
            self.ez = False

    @onMqtt("reset")
    @onMqtt("sand/reset")
    async def res(self, message):
        await self.e.MQTT.publish('game/sand/control', json.dumps( {self.address:[0,0,0,0, 0,0,0,0]}).encode(), qos=QOS_2, retain=True)
        await asyncio.sleep(2)
        self.ez = False
        self.triggered = [False, False, False, False]
        self.final = False

