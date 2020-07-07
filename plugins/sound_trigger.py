from wrappers import plugin, onMqtt, regex, service
from main import ERM
import os
from hbmqtt.mqtt.constants import QOS_2
from soundsystem import sound
import asyncio

@plugin
class myPlugin2:
    def __init__(self, e: ERM):
        self.e = e
        self.e.player.after_callback = self.soundend
        self.e.player.before_callback = self.soundstart

    async def soundstart(self, s: sound):
        await self.e.MQTT.publish('game/sounds/playing', s.sound_id.encode(), qos=QOS_2)

    async def soundend(self, s: sound):
        await self.e.MQTT.publish('game/sounds/finished', s.sound_id.encode(), qos=QOS_2)


    @service
    async def foo(self):
        while 1:
            if self.e.player.sounds:
                await self.e.MQTT.publish('game/sounds/during', " ".join([s.sound_id + " " + str(round(s.progress*100)) for s in self.e.player.sounds.values() if not s.stopped]).encode(), qos=QOS_2)
            await asyncio.sleep(0.2)


    @onMqtt("sounds/stop")
    async def stopsound(self, message):
        sound_id = message.publish_packet.payload.data.decode()
        print("I should stop: ", sound_id)
        if sound_id in self.e.player.sounds:
            self.e.player.sounds[sound_id].stop()
        else:
            print("not found")

    @onMqtt("sounds/playpause")
    async def playpause(self, message):
        sound_id = message.publish_packet.payload.data.decode()
        print("I should p/p: ", sound_id)
        if sound_id in self.e.player.sounds:
            self.e.player.sounds[sound_id].playpause()
        else:
            print("not found")

    @onMqtt("sounds/volume")
    async def changevolume(self, message):
        sounds, _, volume = message.publish_packet.payload.data.decode().rpartition(" ")
        volume = int(volume)/100.0
        sounds = sounds.split()
        if sounds:
            for sound_id in sounds:
                if sound_id in self.e.player.sounds:
                    self.e.player.sounds[sound_id].volume = volume
        else:
            self.e.player.master_volume = volume



    @regex(r"sounds/play/(?P<word>.+)")
    async def play(self, message, match):
        sound, _, options = message.publish_packet.payload.data.decode().partition(" ")
        loops, _, options = options.partition(" ")
        volume, _, options = options.partition(" ")

        if not loops:
            loops = 1
        else:
            loops = int(loops)

        if not volume:
            volume = 1.0
        else:
            volume = int(volume)/100.0

        file = "www/static/sounds/" + sound
        if os.path.exists(file):
            speakers_ = match.group(1).split(",")
            speakers = set()
            for speaker in speakers_:
                if speaker in self.e.speakergroups:
                    for s in self.e.speakergroups[speaker]:
                        speakers.add(s)
                elif speaker in self.e.speakers:
                    speakers.add(speaker)

            if speakers:
                actual = [self.e.speakers.index(x) for x in speakers]

                await self.e.player.playsound(actual, file, loops=loops, volume=volume)
