
import inspect
import crontab
import functools

def plugin(_class):
    _class._plugin = True
    _class._name = _class.__name__
    return _class

def wrapinner(func):
    if inspect.iscoroutinefunction(func):
        outfunc = func
    else:
        @functools.wraps(func)
        async def outfunc(*_):
            func(*_)
    return outfunc


def cron(cr=None):
    def wrapper(func):
        if hasattr(func, '_crons'):
            func._crons.append(cr)
            return func
        func._crons = [cr]
        return wrapinner(func)
    if type(cr) is not str:
        raise Exception("incorrect or no cron specified")
    return wrapper


def onMqtt(topic=None):
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
            _func._topics.append(name)
            return _func
        _func._commands = [name]
        return wrapinner(_func)

    if inspect.isfunction(topic):
        return wrapper(topic)
    else:
        return wrapper


def service(servicename=None):
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
        return wrapinner(_func)

    if inspect.isfunction(servicename):
        return wrapper(servicename)
    else:
        return wrapper

def www(url):
    pass