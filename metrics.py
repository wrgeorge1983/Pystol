'''
Created on Dec 1, 2014

@author: William.George
'''
import time

DEBUG = False
METRICS = {}
VERBOSITY = 0
StartTime = 0


def UpdateMetric(metric='default'):
    ''' Given a metric name as a string, increment its counter'''
    if metric not in METRICS:
        METRICS[metric] = 0
    METRICS[metric] += 1
    if DEBUG:
        print metric, METRICS[metric]


def PrintMetrics():
    ''' Print metrics previously stored with 'UpdateMetric' '''
    for k in sorted(METRICS):
        print k, METRICS[k]


def DebugPrint(msg, level=1):
    levelNames = {0: 'DEBUG', 1: 'INFO', 2: 'STATUS', 3: 'ERROR'}
    if level >= (3 - VERBOSITY):
        print '{0}:{1}'.format(levelNames[level], msg)


def Clock(start=False):
    global StartTime
    if start or not StartTime:
        StartTime = time.time()
        return
    else:
        return time.time() - StartTime


if __name__ == '__main__':
    pass
