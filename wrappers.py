import inspect
import crontab
import functools
import concurrent.futures
import asyncio

def plugin(_class):
    _class._plugin = True
    _class._name = _class.__name__
    return _class


def asyncrunner(func, args):
    newloop = asyncio.new_event_loop()
    newloop.run_until_complete(func(*args))


def wrapinner(func, runlevel=0):
    if runlevel > 0:
        if runlevel == 1:
            ex = concurrent.futures.ThreadPoolExecutor
        else:
            ex = concurrent.futures.ProcessPoolExecutor

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def wrappedfunc(*_):
                loop = asyncio.get_running_loop()

                with ex() as pool:
                    await loop.run_in_executor(pool, asyncrunner, func, _)
        else:
            @functools.wraps(func)
            async def wrappedfunc(*_):
                loop = asyncio.get_running_loop()

                with ex() as pool:
                    await loop.run_in_executor(pool, func, *_)

        @functools.wraps(func)
        async def foo(*_):
            loop = asyncio.get_running_loop()
            loop.create_task(wrappedfunc(*_))

        final = foo
    else:
        if inspect.iscoroutinefunction(func):
            outfunc = func
        else:
            @functools.wraps(func)
            async def outfunc(*_):
                func(*_)
        final = outfunc

    return final


def cron(cr=None, runlevel=0):
    def wrapper(func):
        if hasattr(func, '_crons'):
            func._crons.append(cr)
            return func
        func._crons = [cr]
        return wrapinner(func, runlevel=runlevel)
    if type(cr) is not str:
        raise Exception("incorrect or no cron specified")
    return wrapper


def onMqtt(topic=None, qos=0, runlevel=0):
    def wrapper(_func):
        if inspect.isfunction(topic):
            name = topic.__name__
        elif topic is None:
            name = _func.__name__
        else:
            name = topic

        if str(name).startswith("on"):
            name = name[2:]

        if hasattr(_func, '_topics'):
            _func._topics.append()
            return _func
        _func._topics = [(name, qos)]
        return wrapinner(_func, runlevel=runlevel)

    if inspect.isfunction(topic):
        return wrapper(topic)
    else:
        return wrapper


def regex(topic, pattern, qos, flags=0, runlevel=0):
    def wrapper(_func):
        if hasattr(_func, '_regexes'):
            _func._regexes.append((topic, pattern, flags))
            return _func
        _func._commands = [(topic, qos, pattern)]
        return wrapinner(_func, runlevel=runlevel)

    return wrapper


def trigger(topic, trigger_, runlevel=0):
    def wrapper(func):
        if hasattr(func, '_triggers'):
            func._triggers.append((topic, trigger_))
            return func
        func._triggers = [(topic, trigger_)]
        return wrapinner(func, runlevel=runlevel)
    if trigger is None:
        raise Exception("no trigger specified")
    else:
        return wrapper


def service(servicename=None, runlevel=0):
    def wrapper(_func):
        if inspect.isfunction(servicename):
            name = servicename.__name__
        elif servicename is None:
            name = _func.__name__
        else:
            name = servicename
        if hasattr(_func, "_services"):
            _func._services.append(name)
            return _func

        _func._services = [name]
        return wrapinner(_func, runlevel=runlevel)

    if inspect.isfunction(servicename):
        return wrapper(servicename)
    else:
        return wrapper


def www(route=None):
    def wrapper(_func):
        if inspect.isfunction(route):
            route_ = "/"+route.__name__
        elif route is None:
            route_ = "/"+_func.__name__
        else:
            route_ = route

        if not hasattr(_func, "_www"):
            _func._www = []
        _func._www.append(route_)
        return _func
    if inspect.isfunction(route):
        return wrapper(route)
    else:
        return wrapper
