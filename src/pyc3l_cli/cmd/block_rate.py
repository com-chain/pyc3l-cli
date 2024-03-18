#!/usr/bin/env python
"""Monitors block rate"""

import click
import time

from pyc3l import Pyc3l
from pyc3l_cli import common


@click.command()
@click.option("-d", "--duration",
              help="stop monitoring after given minutes",
              default=None,
              type=int)
@click.option("-D", "--delay", help="delay between blockchain request in seconds", default=2)
@click.option("-e", "--endpoint",
              help="Force com-chain endpoint")
def run(duration, delay, endpoint):

    pyc3l = Pyc3l(endpoint)

    start = time.time()

    # test run
    blocks = []
    deltas = []
    msg = (f"Run will stop in {duration} min"
           if duration else
           "Cancel run with Ctrl-C.")
    print(f"Starting the run. {msg}")
    current_block = pyc3l.getBlockNumber()
    current_block_time = time.time()
    if duration:
        duration = duration * 60
    try:
        while True:
            new_block = pyc3l.getBlockNumber()
            current_time = time.time()
            if new_block > current_block:
                delta = current_time - current_block_time
                current_block_time = current_time
                blocks.append(current_block)
                deltas.append(delta)
                current_block = new_block
                print(f"New block after {common.pp_duration(delta)}")
            if duration and (current_time - start) > duration:
                break
            time.sleep(delay)
    except KeyboardInterrupt:
        pass
    msg = f"During the {common.pp_duration(current_time - start)} run, "
    if blocks:
        msg += (
            f"{len(blocks)} blocks where added. " +
            f"Average delay for new block is {common.pp_duration(sum(deltas) / len(blocks))}"
        )
    else:
        msg += "No blocks where added !"
    print(msg)
