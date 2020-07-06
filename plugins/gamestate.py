from wrappers import plugin, cron, service, onMqtt, www
import asyncio
import logging
from main import ERM
import datetime
from hbmqtt.mqtt.constants import QOS_1, QOS_2

@plugin
class myPlugin2:
    def __init__(self, e: ERM):
        self.e = e
        self.timer = datetime.timedelta(hours=1)
        self.going = asyncio.Event()

    @service
    async def timertick(self):
        while 1:
            await self.going.wait()
            self.timer -= datetime.timedelta(seconds=1)
            minutes, seconds = divmod(self.timer.total_seconds(), 60)
            await self.e.MQTT.publish('game/timer/current', "{:02d}:{:02d}".format(int(minutes), int(seconds)).encode(), qos=QOS_2)
            await asyncio.sleep(1)

    @onMqtt('timer/current')
    async def time(self, message):
        pass

    @onMqtt('timer/relative')
    async def rel(self, message):
        packet = message.publish_packet
        d: bytearray = packet.payload.data
        self.timer += datetime.timedelta(seconds=int(d.decode()))

    @onMqtt('timer/control')
    async def timer_control(self, message):
        d = message.publish_packet.payload.data.decode()
        print(d)
        if d == "start":
            self.going.set()
        elif d == "stop":
            self.going.clear()
        elif d == "toggle":
            if self.going.is_set():
                self.going.clear()
            else:
                self.going.set()
