from wrappers import plugin, onMqtt, regex
from main import ERM
import os
from hbmqtt.mqtt.constants import QOS_2
from soundsystem import sound

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


    @regex(r"sounds/clue/(?P<word>.+)")
    async def clue(self, message, match):
        file = "www/static/sounds/clues/" + message.publish_packet.payload.data.decode()
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

                await self.e.player.playsound(actual, file)
