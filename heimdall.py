#!/usr/bin/python
"""
Heimdall is a tool for limiting network traffic within a rolling-window.

It will monitor network intensive processes, and suspend them if they're
approaching the limits.

"""

__version_info__ = (0, 1, 0)
__version__ = '.'.join(str(num) for num in __version_info__)

from datetime import datetime, timedelta
from dateutil.parser import parse
from os import path
from psutil.error import NoSuchProcess
from time import sleep
from utils import readable_to_bytes, bytes_to_readable
import logging
import psutil
import yaml
import sys

config = None
usage = []
suspended = set()
horn = None

class Gjallarhorn(object):
    """ When the horn is blown, all listeners will hear the sound."""

    def __init__(self, *args):
        self.funcs = list(args)

    def add_listener(self, func):
        self.funcs.append(func)

    def blow(self, sound):
        for func in self.funcs:
            func(sound)

def init():
    _load_config()
    _set_defaults()
    _init_logging()
    _print_startup_info()
    _update_usage_log()
    _init_horn()
    logging.debug('Config values:')
    for key, val in config.items():
        logging.debug('{} -> {}'.format(key, val))

def run():
    last_value = _get_window_usage()
    while True:
        last_value = limit(last_value)
        sleep(config['monitor_interval_in_s'])

def limit(last_value):
    usage_limit = config['limit_in_bytes']
    past_usage = _get_window_usage()
    total = psutil.network_io_counters().bytes_sent
    logging.debug("Bytes sent: {}".format(bytes_to_readable(total)))
    usage_delta = total - past_usage
    logging.debug("Delta: {}".format(usage_delta))
    pids = psutil.get_pid_list()
    for pid in pids:
        try:
            process = psutil.Process(pid)
            if process.name.lower() in config['watch_list']:
                if past_usage >= usage_limit:
                    if pid not in suspended:
                        sound = 'Suspending process: {} ({})'.format(process.name, pid)
                        horn.blow(sound)
                        process.suspend()
                        suspended.add(pid)
                else:
                    for pid in suspended:
                        proc = psutil.Process(pid)
                        sound = 'Resuming process: {}'.format(proc.name)
                        horn.blow(sound)
                        proc.resume()
                    suspended.clear()
        except NoSuchProcess:
            logging.debug('Process was terminated externally: %s' % pid)
            continue
    usage.append( (datetime.now(), usage_delta) )
    with open('usage_log.log', 'a') as usage_log:
        usage_log.write('{} {}\n'.format(datetime.now().isoformat(), usage_delta))
    return usage_delta

def _load_config():
    global config
    mode = 'r' if path.exists('config.yaml') else 'w+'
    with open('config.yaml', mode) as config_file:
        config = yaml.load(config_file) or {}

def _set_defaults():
    if config.get('watch_list') is None:
        print('Quitting: You must specify a watch_list in config.yaml!')
        sys.exit(1)
    limit_in_bytes = readable_to_bytes(config.get('limit', '10 GB'))
    config.setdefault('limit_in_bytes', limit_in_bytes)
    config.setdefault('log_file', 'log.log')
    config['watch_list'] = set([p.lower() for p in config.get('watch_list', [])])
    config.setdefault('monitor_interval_in_s', 5)
    config.setdefault('window_size_in_h', 24)

def _init_logging():
    msg_format = '%(asctime)s %(levelname)-10s %(message)s'
    logging.basicConfig(format=msg_format, level=logging.DEBUG)
    file_handler = logging.FileHandler(config['log_file'])
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(msg_format))
    logging.getLogger().addHandler(file_handler)

def _print_startup_info():
    logging.info('Heimdall version {} running.'.format(__version__))
    logging.info('Logging to {}'.format(config['log_file']))
    logging.debug('Will limit following processes if high load:')
    for process in config['watch_list']:
        logging.debug(process)

def _get_window_usage():
    """ Search serially upwards to first value registered within the window.

    The first value should be among the very first in most cases, so no need
    to do binary search."""
    limit_date = datetime.now() - timedelta(seconds=config['window_size_in_h'])
    first_valid_index = -1
    for index, (date, val) in enumerate(usage):
        if date >= limit_date:
            first_valid_index = index
            break
    window_usage = sum(val for date, val in usage[first_valid_index:])
    del usage[:first_valid_index]
    print('Window: ' + str(["%s: %s" % (d.strftime("%H:%M:%S"), t) for d, t in usage]))
    return window_usage

def _update_usage_log():
    if path.exists('usage_log.log'):
        limit_date = datetime.now() - timedelta(seconds=config['window_size_in_h'])
        with open('usage_log.log', 'r') as usage_log:
            for line in usage_log:
                datestring, val = line.split()
                date = parse(datestring)
                if date >= limit_date:
                    usage.append( (date, int(val)) )
        with open('usage_log.log', 'w') as usage_log:
            for date, val in usage:
                usage_log.write('{} {}\n'.format(date.isoformat(), val))
    else:
        open('usage_log.log', 'w').close()

def _init_horn():
    global horn
    horn = Gjallarhorn(logging.info)
    if sys.platform == 'win32':
        #TODO: Find a tool to make notifications on windows
        pass
    elif sys.platform == 'darwin': #Mac
        try:
            from pync import Notifier
            horn.add_listener(Notifier.notify)
        except ImportError:
            pass

if __name__ == '__main__':
    try:
        init()
        run()
    except Exception as e:
        for pid in suspended:
            logging.debug("Resuming processes: {}".format(suspended))
            process = psutil.Process(pid)
            process.resume()
        logging.exception(e.message)
        info = sys.exc_info()
        raise (info[0], info[1], info[2])