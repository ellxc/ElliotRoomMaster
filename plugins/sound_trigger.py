from wrappers import plugin, onMqtt, regex
from main import ERM
import os
from hbmqtt.mqtt.constants import QOS_2

@plugin
class myPlugin2:
    def __init__(self, e: ERM):
        self.e = e

    @onMqtt('sounds/clue')
    async def rel(self, message):
        file = "www/static/sounds/clues/" + message.publish_packet.payload.data.decode()
        if os.path.exists(file):
            await self.e.player.playsound(["system:playback_1", "system:playback_2"], file)



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

                await self.e.MQTT.publish('sounds/playing/clue/'+",".join(speakers), message.publish_packet.payload.data.decode(), qos=QOS_2)
                await self.e.player.playsound(actual, file)
                await self.e.MQTT.publish('sounds/finished/clue/'+",".join(speakers), message.publish_packet.payload.data.decode(), qos=QOS_2)
