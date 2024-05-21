#!/usr/bin/env python

import click
from typing import Optional

from pyc3l import Pyc3l
from .. import common


@click.command()
@click.option("-e", "--endpoint", help="Force com-chain endpoint.")
@click.option("-n", "--count", type=int, help="Number of block to show after the current one.", default=1)
@click.option("-r", "--raw", is_flag=True, help="Print raw values.")
@click.option("-E", "--skip-empty", is_flag=True, help="Skip empty blocks.")
@click.argument("block_nb", required=False)
def run(block_nb: Optional[str], endpoint: Optional[str], count: int, raw: bool, skip_empty: bool):

    pyc3l = Pyc3l(endpoint)

    block_nb = pyc3l.getBlockNumber() if block_nb is None else \
        int(block_nb, 16) if block_nb.startswith("0x") else \
        int(block_nb)
    block = pyc3l.BlockByNumber(block_nb + 1)

    if not raw:
        common.pp_seg_blocks = common.protect_tty(common.pp_seg_blocks)

    common.pp_seg_blocks(block, count, raw, skip_empty)


if __name__ == "__main__":
    run()







