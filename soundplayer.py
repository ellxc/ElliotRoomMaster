import jack
import soundfile as sf
import numpy as np
import asyncio
import itertools
import janus
import random
import traceback, sys
import time
import concurrent.futures

class soundplayer:
    def __init__(self, ins, filename, loops=1, volume=1.0, key=None, fadein=False, fadetime=1, clientname="foo", sounddevices=None, buffsize=20, loop=None):
        self.loop = loop
        self.loops = loops
        self.volume = volume
        self.fadein = fadein
        self.fadetime = fadetime
        self.outs = {}
        self.filename = filename
        self.sound_id = None
        if key is None:
            self.sound_id = filename.rpartition("/")[2] + "_" + str(random.choice(range(999)))
        else:
            self.sound_id = str(key)
        self.sound = None
        self.ins = ins
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

    async def run(self):
        self.client = jack.Client(self.clientname, no_start_server=True)
        self.blocksize = self.client.blocksize
        self.client.set_process_callback(self.make_proccess())
        self.client.activate()
        outports = []
        qs = []
        for i, in_set in enumerate(self.ins):
            print(in_set)
            if in_set:
                outport = self.client.outports.register(self.sound_id + "_" + str(i))
                inports = self.client.get_ports(is_input=True, is_audio=True)
                for in_no in in_set:
                    outport.connect(inports[in_no])
                outports.append(outport)
                qs.append(janus.Queue(maxsize=20))
            else:
                outports.append(None)
                qs.append(None)
        self.sound = sound(self.filename, qs, outports, sound_id=self.sound_id, loops=self.loops, volume=self.volume, blocksize=self.blocksize,
                  dtype='float32', always_2d=True, fill_value=0, fadein=self.fadein, fadetime=self.fadetime)
        async for p in self.sound.run():
            pass
        print("finished")

    def make_proccess(self):
        def process(frames):
            try:
                if self.sound == None:
                    return
                if not self.sound.paused and not self.sound.stopped and self.sound.volume > 0.1:
                    for o, q in itertools.zip_longest(self.sound.outports, self.sound.qs, fillvalue=None):
                        try:
                            if o is not None and q is not None:
                                o.get_array()[:] = q.sync_q.get_nowait() * self.sound.volume * self.master_volume
                                continue
                        except janus.SyncQueueEmpty:
                            pass
                    return
                if self.sound.stopped:
                    try:
                        for q in self.sound.qs:
                            q.sync_q.get_nowait()
                    except janus.SyncQueueEmpty:
                        pass
                        #if s.sound_id in self.sounds:
                         #   del self.sounds[s.sound_id]
                for o in self.sound.outports:
                    if o is not None:
                        o.get_array()[:] = np.zeros((self.blocksize,), dtype='float32')
            except Exception as e:
                print("EXCEPTION!!!: ", type(e), e)

        return process


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

def playsong(filename, speakers):
    l = asyncio.get_event_loop()
    b = soundplayer(speakers, filename, loops=2)
    l.run_until_complete(b.run())


if __name__=="__main__":
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        pool.submit(playsong, "tc.ogg", [[0, 1]])
        pool.submit(playsong, "tc.ogg", [[2, 3]])
        pool.submit(playsong, "tc.ogg", [[4, 5]])
        pool.submit(playsong, "tc.ogg", [[6, 7]])
        pool.submit(playsong, "tp.ogg", [[8, 9]])
        #pool.submit(playsong, "tp.ogg", [[10, 11]])
       # pool.submit(playsong, "tp.ogg", [[12, 13]])
        #pool.submit(playsong, "tp.ogg", [[14, 15]])
