
import jack
import soundfile as sf
import numpy as np
import asyncio
import itertools
import janus
import random
import traceback, sys
import time


class JackClientNotStarted(Exception):
    ...


class JackNPlayer:
    def __init__(self, clientname="foo", sounddevices=None, buffsize=20, loop=None):
        self.loop = loop
        self.outs = {}
        self.soundfiles = {}
        self.insnouts = []
        self.sounds = {}
        self.clientname = clientname
        self.buffsize = buffsize
        self.client = None
        self.blocksize = None
        self.samplerate = None
        self.jack_running = asyncio.Event()
        self.client_started = asyncio.Event()
        self.sounddevices = sounddevices if sounddevices is not None else []

        self.before_callback = None
        self.during_callback = None
        self.during_callback_freq = 5
        self.after_callback = None

        self.master_volume = 1.0

    def make_proccess(self):
        def process(frames):
            try:
                s: sound
                for s in list(self.sounds.values()):
                    if not s.paused and not s.stopped and s.volume > 0.1:
                        for o, q in itertools.zip_longest(s.outports, s.qs, fillvalue=None):
                            try:
                                if o is not None and q is not None:
                                    o.get_array()[:] = q.sync_q.get_nowait() * s.volume * self.master_volume
                                    continue
                            except janus.SyncQueueEmpty:
                                pass
                        continue
                    if s.stopped:
                        try:
                            for q in s.qs:
                                q.sync_q.get_nowait()
                        except janus.SyncQueueEmpty:
                            if s.sound_id in self.sounds:
                                del self.sounds[s.sound_id]
                    for o in s.outports:
                        if o is not None:
                            o.get_array()[:] = np.zeros((self.blocksize,), dtype='float32')
            except Exception as e:
                print("EXCEPTION!!!: ", type(e), e)

        return process

    async def run(self):
        await self.runclient()

    async def runclient(self):
        self.client = jack.Client(self.clientname, no_start_server=True)
        self.blocksize = self.client.blocksize
        self.client.set_process_callback(self.make_proccess())
        self.client.activate()
        self.client_started.set()

    async def playsound(self, ins, filename, loops=1, volume=1.0, key=None, fadein=False, fadetime=1):
        await self.client_started.wait()
        if key is None:
            sound_id = filename.rpartition("/")[2] + "_" + str(random.choice(range(999)))
            while sound_id in self.sounds:
                sound_id = filename.rpartition("/")[2] + "_" + str(random.choice(range(999)))
        else:
            sound_id = str(key)
        outports = []
        qs = []
        for i, in_set in enumerate(ins):
            if in_set:
                outport = self.client.outports.register(sound_id+"_"+str(i))
                inports = self.client.get_ports(is_input=True, is_audio=True)
                for in_no in in_set:
                    outport.connect(inports[in_no])
                outports.append(outport)
                qs.append(janus.Queue(maxsize=40))
            else:
                outports.append(None)
                qs.append(None)
        s = sound(filename, qs, outports, sound_id=sound_id, loops=loops, volume=volume, blocksize=self.blocksize,
                  dtype='float32', always_2d=True, fill_value=0, fadein=fadein, fadetime=fadetime)

        self.sounds[sound_id] = s

        if self.before_callback is not None:
            await self.before_callback(s)
        try:
            c = 0
            async for p in s.run():
                if self.during_callback is not None:
                    n = round(p*100)
                    if abs(n - c) > self.during_callback_freq:
                        c = n
                        self.loop.create_task(self.during_callback(s, p))
        except:
            traceback.print_exc(file=sys.stdout)
        if self.after_callback is not None:
            await self.after_callback(s)

        if s.sound_id in self.sounds:
            del self.sounds[s.sound_id]

    async def pausesound(self):
        pass

    async def stopsound(self):
        pass


class sound():
    def __init__(self, filename, qs, outports, sound_id, start_paused=False, loops=1, volume=1.0, fadein=False, fadetime=1, **kwargs):
        self.sound_id = sound_id
        self.qs = qs
        self.outports = outports
        self.filename = filename
        self.sf = sf.SoundFile(self.filename)



        self.loops = loops
        self._volume = volume
        self.kwargs = kwargs
        self._paused = asyncio.Event()
        if not start_paused:
            self._paused.set()

        self._stop = False
        self._current = 0

        self._fadingout = False
        self._fadingin = fadein
        self._fadetime = fadetime
        self._fadefrom = time.time()


    def play(self):
        self._paused.set()

    def pause(self):
        self._paused.clear()

    def fadeout(self, timer=1):
        self._fadingin = False
        self._fadingout = True
        self._fadetime = timer
        self._fadefrom = time.time()

    def fadein(self, timer=1):
        self._paused.set()
        self._fadingout = False
        self._fadingin = True
        self._fadetime = timer
        self._fadefrom = time.time()

    @property
    def volume(self):
        if self._fadingout:
            x = time.time() - self._fadefrom
            if x > self._fadetime:
                self.pause()
                self._fadingout = False
                return 0
            else:
                return self._volume * ((self._fadetime - x)/self._fadetime)
        if self._fadingin:
            x = time.time() - self._fadefrom
            if x < self._fadetime:
                return self._volume * (x/self._fadetime)
            else:
                self._fadingin = False
        return self._volume

    @volume.setter
    def volume(self, vol):
        self._volume = vol

    @property
    def paused(self):
        return not self._paused.is_set()

    @property
    def stopped(self):
        return self._stop

    def playpause(self):
        if self._paused.is_set():
            self._paused.clear()
        else:
            self._paused.set()

    def stop(self):
        self._stop = True
        if not self._paused.is_set():
            self._paused.clear()

    def restart(self):
        self.sf.seek(0)

    def cleanup(self):
        self.sf.close()
        for o in self.outports:
            o.unregister()



    @property
    def progress(self):
        return self._current/self.sf.frames

    async def run(self):
        print(self.qs, self.outports)
        blocksize = self.kwargs.get("blocksize")
        for _ in range(self.loops) if self.loops > 0 else itertools.cycle([0]):
            if self.stopped:
                break
            while self._current + blocksize < self.sf.frames:
                if self.stopped:
                    break
                self.sf.seek(self._current)
                for i, channel in enumerate(self.sf.read(blocksize, always_2d=True).T):
                    if i >= len(self.qs):
                        break
                    if self.qs[i] is not None:
                        await self.qs[i].async_q.put(channel)
                self._current += blocksize
                yield self.progress
            self.sf.seek(0)
            self._current = 0
        print("file finished")
        await asyncio.sleep(1)
        self.cleanup()


if __name__=="__main__":
    l = asyncio.get_event_loop()
    b = JackNPlayer()
    l.create_task(b.run())
    l.create_task(b.playsound([0, 1, 3, 7], "tc.ogg", loops=2))
    l.create_task(b.playsound([8, 9, 12, 13], "tp.ogg", volume=2))
    l.run_forever()
