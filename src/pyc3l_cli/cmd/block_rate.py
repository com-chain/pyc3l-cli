#!/usr/bin/env python
"""Monitors block rate"""


from pyc3l.ApiCommunication import ApiCommunication
from datetime import datetime, timedelta
import time

# load the high level functions
api_com = ApiCommunication("Lemanopolis")


# configure run
test_duration = 20  # [min]
step = 2  # [sec]

number = int((test_duration * 60) / step)

# test run
blocks = []
dt = []
print("Starting the run. See you in " + str(test_duration) + " min")
start_block = api_com.getBlockNumber()
start_time = datetime.now()
for counter in range(number):
    curr_block = api_com.getBlockNumber()
    curr_time = datetime.now()
    if curr_block > start_block:
        delta = curr_time - start_time
        sec = delta.total_seconds()
        blocks.append(start_block)
        dt.append(sec)
        start_block = curr_block
        start_time = curr_time
        print("New block after " + str(sec) + " s")
    time.sleep(step)

# output result
total_block = len(blocks)

print(
    "During the "
    + str(test_duration)
    + " min run "
    + str(total_block)
    + " blocks where added average delay ="
    + str(sum(dt) / total_block)
    + " s."
)
