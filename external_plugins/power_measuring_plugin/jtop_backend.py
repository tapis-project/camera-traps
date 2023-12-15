from jtop import jtop
import json
import time
import os
import sys

log_dir = os.environ['TRAPS_POWER_LOG_PATH']
file_name = 'jtop_log.json'


def read_stats(jetson):
    log_file = os.path.join(log_dir, file_name)
    data = jetson.power
    data['date'] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(data)
    log = json.loads(open(log_file, 'r').read())
    log.append(data)
    open(log_file, 'w').write(json.dumps(log))


def jtop_measure():
    log_file = os.path.join(log_dir, file_name)
    if not os.path.exists(log_file):
        open(log_file, 'w').write('[]')
    with jtop() as jetson:
        if jetson.ok():
            read_stats(jetson)
