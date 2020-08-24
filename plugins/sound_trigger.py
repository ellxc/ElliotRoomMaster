import sys
if sys.platform != "win32":

    from wrappers import plugin, onMqtt, regex, service, onconfig
    from main import ERM
    import os
    from hbmqtt.mqtt.constants import QOS_2
    from soundsystem import sound
    import asyncio
    import json
    import queue

    @plugin
    class myPlugin2:
        def __init__(self, e: ERM):
            self.e = e
            self.e.player.after_callback = self.soundend
            self.e.player.before_callback = self.soundstart
            self.play_next = asyncio.Event()
            self.play_next.set()

            self.q = []
            self.qpos = 0

            self.skipping = False
            self.soundtrack = False

        @onconfig
        def setupsoundtrack(self):
            if "controls" in self.e.config:
                if "sounds" in self.e.config["controls"]:
                    if "soundtrack" in self.e.config["controls"]["sounds"]:
                        for s in self.e.config["controls"]["sounds"]["soundtrack"]:
                            print(s)
                            speakers = set()
                            if type(s["speakers"]) == list and s["speakers"] and type(s["speakers"][0]) == list:
                                for group in s["speakers"]:
                                    groupset = set()
                                    for speaker in group:
                                        if speaker in self.e.speakergroups:
                                            for spk in self.e.speakergroups[speaker]:
                                                groupset.add(spk)
                                        elif speaker in self.e.speakers:
                                            groupset.add(speaker)
                                    speakers.add(groupset)
                                actual = [[self.e.speakers.index(x) for x in speakergroup] for speakergroup in speakers]
                            elif type(s["speakers"]) == str:
                                if s["speakers"] in self.e.speakergroups:
                                    if s["speakers"] in self.e.speakergroups:
                                        for spk in self.e.speakergroups[s["speakers"]]:
                                            speakers.add(spk)
                                    elif s["speakers"] in self.e.speakers:
                                        speakers.add(s["speakers"])
                                actual = [[self.e.speakers.index(x) for x in speakers]]
                            else:
                                for speaker in s["speakers"]:
                                    if speaker in self.e.speakergroups:
                                        for spk in self.e.speakergroups[speaker]:
                                            speakers.add(spk)
                                    elif speaker in self.e.speakers:
                                        speakers.add(speaker)
                                actual = [[self.e.speakers.index(x) for x in speakers]]

                            self.q.append(("www/static/sounds/soundtracks/"+s["filename"], actual))

        async def soundstart(self, s: sound):
            await self.e.MQTT.publish('game/sounds/playing', s.sound_id.encode(), qos=QOS_2)

        async def soundend(self, s: sound):
            await self.e.MQTT.publish('game/sounds/finished', s.sound_id.encode(), qos=QOS_2)


        @service
        async def foo(self):
            while 1:
                if self.e.player.sounds:
                    x = " ".join([s.sound_id + " " + str(round(s.progress*100)) for s in self.e.player.sounds.values()
                                  if not s.stopped and not s.paused])
                    if x:
                        await self.e.MQTT.publish('game/sounds/during', x.encode(), qos=QOS_2)
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
                if self.e.player.sounds[sound_id].paused:
                    await self.e.MQTT.publish('game/sounds/paused', sound_id.encode(), qos=QOS_2, retain=True)
                else:
                    await self.e.MQTT.publish('game/sounds/resumed', sound_id.encode(), qos=QOS_2, retain=True)
            else:
                print("not found")

        @onMqtt("sounds/fadeout")
        async def fadeout(self, message):
            sound_id = message.publish_packet.payload.data.decode()
            print("I should fadeout: ", sound_id)
            if sound_id in self.e.player.sounds:
                self.e.player.sounds[sound_id].fadeout()
            else:
                print("not found")


        @onMqtt("sounds/fadein")
        async def fadein(self, message):
            sound_id = message.publish_packet.payload.data.decode()
            print("I should fadein: ", sound_id)
            if sound_id in self.e.player.sounds:
                self.e.player.sounds[sound_id].fadein()
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

        @onMqtt("soundtrack/start")
        async def startsoundtrack(self, message):
            if self.soundtrack:
                print("soundtrack already going")
                return

            print("starting soundtrack...")
            first = self.e.player.playsound(self.q[self.qpos][1],
                                            self.q[self.qpos][0],
                                            loops=-1, volume=1, fadein=True)
            second = None
            s: sound
            r, s = await type(first).__aenter__(first)
            r2, s2 = None, None
            while 1:
                stop = False

                if r is not None:
                    try:
                        await r.__anext__()
                    except StopAsyncIteration:

                        stop = True
                else:
                    print("end of queue")
                    self.qpos = 0
                    break

                if r2 is not None:
                    try:
                        await r2.__anext__()
                    except StopAsyncIteration:
                        pass  # THIS SHOULD NEVER HAPPEN

                if s is not None and (s.stopped or stop or self.skipping and s.paused):
                    s.stop()
                    print("stopping first")
                    await type(first).__aexit__(first, None, None, None)
                    first = second
                    second = None
                    r, s = r2, s2
                    r2, s2 = None, None
                    self.play_next.set()
                    self.skipping = False

                if r2 is not None:
                    try:
                        await r2.__anext__()
                    except StopAsyncIteration:
                        pass  # THIS SHOULD NEVER HAPPEN
                if not self.play_next.is_set() and not self.skipping:
                    if self.qpos + 1 >= len(self.q):
                        print("can't skip to nothing!")
                        self.play_next.set()
                        continue

                    print("skipping")
                    self.skipping = True
                    print(self.q)
                    print(self.qpos)
                    print("next up: {}".format(self.q[self.qpos]))
                    self.qpos += 1
                    s.fadeout()
                    second = self.e.player.playsound(self.q[self.qpos][1], self.q[self.qpos][0],
                                                     loops=-1, volume=1, fadein=True, start_paused=False)
                    r2, s2 = await type(second).__aenter__(second)

        @onMqtt("soundtrack/next")
        async def ASDSDFDSA(self, message):
            self.play_next.clear()
            await self.play_next.wait()

        @onMqtt(r"sounds/play")
        async def play(self, message):
            dat = json.loads(message.publish_packet.payload.data.decode())
            sound = dat["filename"]
            speakers = dat["speakers"]
            loops = int(dat["loops"]) if "loops" in dat else 1
            volume = int(dat["volume"])/100.0 if "volume" in dat else 1.0
            fadein = dat["fadein"] if "fadein" in dat else False
            fadeintime = dat["fadeintime"] if "fadeintime" in dat else 1.0
            startpaused = dat["paused"] if "paused" in dat else False
            #sound, _, options = message.publish_packet.payload.data.decode().partition(" ")
            #loops, _, options = options.partition(" ")
            #volume, _, options = options.partition(" ")


            file = "www/static/sounds/" + sound
            if os.path.exists(file):
                speakers_ = speakers
                speakers = set()
                for speaker in speakers_:
                    if speaker in self.e.speakergroups:
                        for s in self.e.speakergroups[speaker]:
                            speakers.add(s)
                    elif speaker in self.e.speakers:
                        speakers.add(speaker)

                if speakers:
                    actual = [self.e.speakers.index(x) for x in speakers]
                    async with self.e.player.playsound([actual], file, loops=loops, volume=volume, fadein=fadein,
                                                       fadetime=fadeintime, start_paused=startpaused) as (r, s):
                        async for p in r:
                            pass
