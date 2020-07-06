import jack
import soundfile as sf
import numpy as np
import asyncio
import itertools
import janus
import random


class JackClientNotStarted(Exception):
    ...


class JackNPlayer():
    def __init__(self, clientname="foo", sounddevices=None, buffsize=20):
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

    def make_proccess(self):
        def process(frames):
            try:
                for ss in self.sounds.values():
                    for s in ss:
                        try:
                            s.outport.get_array()[:] = s.q.sync_q.get_nowait()
                        except janus.SyncQueueEmpty:
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
        outport = self.client.outports.register(filename + "_" + str(random.choice(range(999)))) # TODO : make actually unique
        inports = self.client.get_ports(is_input=True, is_audio=True)
        for in_no in ins:
            outport.connect(inports[in_no])
        q = janus.Queue(maxsize=40)
        s = sound(filename, q, outport, loops=loops, volume=volume, blocksize=self.blocksize,
                                           dtype='float32', always_2d=True, fill_value=0)
        if filename not in self.sounds:
            self.sounds[filename] = []
        self.sounds[filename].append(s)

        await s.run()

        self.sounds[filename].remove(s)

    async def pausesound(self):
        pass

    async def stopsound(self):
        pass


class sound():
    def __init__(self, filename, q, outport, start_paused=False, loops=1, volume=1.0, **kwargs):
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

    def play(self):
        self._paused.set()

    def pause(self):
        self._paused.clear()

    def stop(self):
        self._stop = True
        if not self._paused.is_set():
            self._paused.clear()

    def restart(self):
        self.sf.seek(0)

    async def run(self):
        for _ in range(self.loops) if self.loops > 0 else itertools.cycle([0]):
            await self._paused.wait()
            if self._stop:
                break
            for x in self.sf.blocks(**self.kwargs):
                await self.q.async_q.put(x.T[0] * self.volume)
            self.sf.seek(0)
        print("file finished")
        await asyncio.sleep(1)
        self.sf.close()
        self.outport.unregister()


if __name__=="__main__":
    l = asyncio.get_event_loop()
    b = JackNPlayer()
    l.create_task(b.run())
    l.create_task(b.playsound([0, 1, 3, 7], "tc.ogg", loops=2))
    l.create_task(b.playsound([8, 9, 12, 13], "tp.ogg", volume=2))
    l.run_forever()
