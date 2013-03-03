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
from math import log
from os import path
from time import sleep
import logging
import psutil
import yaml
import sys

notify = None
if sys.platform == 'win32':
    # Find a tool to make notifications on windows
    pass
elif sys.platform == 'darwin':
    try:
        # Mac, send notifications to message center
        from pync import Notifier
        notify = Notifier.notify
    except ImportError:
        pass

config = None
usage = []
suspended = set()


def init():
    _load_config()
    _set_defaults()
    _init_logging()
    _print_startup_info()
    _update_usage_log()
    logging.debug('Config values:')
    for key, val in config.items():
        logging.debug('{} -> {}'.format(key, val))

def run():
    last_value = _get_window_usage()
    while True:
        last_value = limit(last_value)
        sleep(config['monitor_interval_in_s'])

def limit(last_value):
    limit = config['limit_in_bytes']
    past_usage = _get_window_usage()
    total = psutil.network_io_counters().bytes_sent
    logging.debug("Bytes sent: {}".format(format_size(total)))
    usage_delta = total - past_usage
    logging.debug("Delta: {}".format(usage_delta))
    pids = psutil.get_pid_list()
    for pid in pids:
        process = psutil.Process(pid)
        if process.name.lower() in config['watch_list']:
            if past_usage >= limit:
                if pid not in suspended:
                    msg = 'Suspending process: {}'.format(process.name)
                    logging.info(msg)
                    Notifier.notify(msg)
                    process.suspend()
                    suspended.add(pid)
            else:
                for pid in suspended:
                    proc = psutil.Process(pid)
                    msg = 'Resuming process: {}'.format(proc.name)
                    logging.info(msg)
                    Notifier.notify(msg)
                    proc.resume()
                suspended.clear()
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
    limit_in_bytes = _parse_file_size(config.get('limit', '10 GB'))
    config['limit_in_bytes'] = config.get('limit_in_bytes', limit_in_bytes)
    config['log_file'] = config.get('log_file', 'log.log')
    config['watch_list'] = set([p.lower() for p in config.get('watch_list', [])])
    config['monitor_interval_in_s'] = config.get('monitor_interval_in_s', 5)
    config['window_size_in_h'] = config.get('window_size_in_h', 24)

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

def _parse_file_size(string):
    val, unit = string.split()
    multipliers = {
                   'kB': 10**3,
                   'MB': 10**6,
                   'GB': 10**9,
                   'TB': 10**12,
                   'KiB': 2**10,
                   'MiB': 2**20,
                   'GiB': 2**30,
                   'TiB': 2**40,
                   }
    multiplier = multipliers.get(unit, 1)
    return int(val)*multiplier

def _get_window_usage():
    """ Search serially upwards to first value registered within the window.

    The first value should be among the very first in most cases, so no need
    to do binary search."""
    window_usage = 0
    limit_date = datetime.now() - timedelta(hours=config['window_size_in_h'])
    for index, (date, val) in enumerate(usage):
        if date >= limit_date:
            window_usage = sum(val for date, val in usage[index:])
            break
    return window_usage

def _update_usage_log():
    if path.exists('usage_log.log'):
        limit_date = datetime.now() - timedelta(hours=config['window_size_in_h'])
        with open('usage_log.log', 'r') as usage_log:
            for line in usage_log:
                datestring, val = line.split()
                date = parse(datestring)
                if date >= limit_date:
                    usage.append( (date, int(val)) )
        with open('usage_log.log', 'w') as usage_log:
            for date, val in usage:
                usage_log.write('{} {}'.format(date.isoformat(), val))
    else:
        with open('usage_log.log', 'w'):
            pass

def format_size(num):
    unit_list = zip(['bytes', 'kB', 'MB', 'GB', 'TB', 'PB'], [0, 0, 1, 2, 2, 2])
    if num >= 1:
        exponent = min(int(log(num, 1024)), len(unit_list) - 1)
        quotient = float(num) / 1024**exponent
        unit, num_decimals = unit_list[exponent]
        format_string = '{:.%sf} {}' % (num_decimals)
        return format_string.format(quotient, unit)
    elif num == 0:
        return '0 bytes'
    else:
        return "-" + format_size(-num)

if __name__ == '__main__':
    try:
        init()
        run()
    except Exception as e:
        for pid in suspended:
            logging.debug("Resuming processes: {}".format(suspended))
            process = psutil.Process(pid)
            process.resume()
        info = sys.exc_info()
        raise info[0], info[1], info[2]