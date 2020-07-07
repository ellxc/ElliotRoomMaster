import jack
import soundfile as sf
import numpy as np
import asyncio
import itertools
import janus
import random
import traceback, sys

class JackClientNotStarted(Exception):
    ...


class JackNPlayer():
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
                s :sound
                for s in list(self.sounds.values()):
                    if not s.paused and not s.stopped:
                        try:
                            s.outport.get_array()[:] = s.q.sync_q.get_nowait() * s.volume * self.master_volume
                            continue
                        except janus.SyncQueueEmpty:
                            pass
                    if s.stopped:
                        try:
                            s.q.sync_q.get_nowait()
                        except:
                            if s.sound_id in self.sounds:
                                del self.sounds[s.sound_id]
                    s.outport.get_array()[:] = np.zeros((self.blocksize,), dtype='float32')
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

    async def playsound(self, ins, filename, loops=1, volume=1.0):
        await self.client_started.wait()
        sound_id = filename.rpartition("/")[2] + "_" + str(random.choice(range(999)))
        while sound_id in self.sounds:
            sound_id = filename.rpartition("/")[2] + "_" + str(random.choice(range(999)))
        outport = self.client.outports.register(sound_id)
        inports = self.client.get_ports(is_input=True, is_audio=True)
        for in_no in ins:
            outport.connect(inports[in_no])
        q = janus.Queue(maxsize=40)
        s = sound(filename, q, outport, sound_id=sound_id, loops=loops, volume=volume, blocksize=self.blocksize,
                                           dtype='float32', always_2d=True, fill_value=0)

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
    def __init__(self, filename, q, outport, sound_id, start_paused=False, loops=1, volume=1.0, **kwargs):
        self.sound_id = sound_id
        self.q = q
        self.outport = outport
        self.filename = filename
        self.sf = sf.SoundFile(self.filename)
        self.loops = loops
        self.volume = volume
        self.kwargs = kwargs
        self._paused = asyncio.Event()
        if not start_paused:
            self._paused.set()

        self._stop = False
        self._current = 0

    def play(self):
        self._paused.set()

    def pause(self):
        self._paused.clear()

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
        self.outport.unregister()

    @property
    def progress(self):
        return self._current/self.sf.frames

    async def run(self):
        blocksize = self.kwargs.get("blocksize")
        for _ in range(self.loops) if self.loops > 0 else itertools.cycle([0]):
            if self.stopped:
                break
            while self._current + blocksize < self.sf.frames:
                if self.stopped:
                    break
                self.sf.seek(self._current)
                x = self.sf.read(blocksize)
                await self.q.async_q.put(x)
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
