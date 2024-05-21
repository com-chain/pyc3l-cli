#!/usr/bin/env python
"""Monitors block rate"""

import click
import time
import datetime
import textwrap


from pyc3l import Pyc3l
from pyc3l_cli import common

def now_str():
    return common.dt_to_local_iso(datetime.datetime.now().astimezone())


spinner = "⣷⣯⣟⡿⢿⣻⣽⣾"


def pp_wait_block(pyc3l, duration, delay, raw, blocks, deltas):

    start = time.time()

    if not raw:
        msg = (f"Run will stop in {duration} min"
               if duration else
               "Cancel run with Ctrl-C.")
        print(click.style("Starting the run.", fg="white", bold=True) + f" {msg}")

    current_block_time = time.time()

    current_block_nb = pyc3l.getBlockNumber()
    block = pyc3l.BlockByNumber(current_block_nb)
    if not raw:
        print(
            click.style(f"{now_str()}", fg='cyan') +
            " Current block at startup:"
        )
        print()
        print(textwrap.indent(common.pp_block(block), click.style('  │ ', fg='black')))
        print()
        click.echo(
            click.style(f"\r{now_str()}", fg='cyan') +
            click.style(f" {spinner[0]}",
                        fg='green', bold=True) +
            " Waiting for new block\r",
            nl=False
        )

    first = True
    while True:
        new_block = pyc3l.getBlockNumber()
        current_time = time.time()
        if new_block > current_block_nb:
            delta = current_time - current_block_time
            current_block_time = current_time
            blocks.append(current_block_nb)
            deltas.append(delta)
            current_block_nb = new_block
            block = pyc3l.BlockByNumber(current_block_nb)
            if not raw:
                common.clear_line()
                print(click.style(f"\r{now_str()}", fg='cyan') +
                      " New block after " +
                      click.style(f"{common.pp_duration(delta):>9}", fg='white', bold=True) +
                      ":")
                print()
                print(textwrap.indent(common.pp_block(block), click.style('  │ ', fg='black')))
                print()
            else:
                if first:
                    first = False
                else:
                    print("---")
                print(common.pp_block(block, raw))

        if duration and (current_time - start) > duration:
            break
        if not raw:
            click.echo(
                click.style(f"\r{now_str()}", fg='cyan') +
                click.style(f" {spinner[int((current_time - start) / delay) % len(spinner)]}",
                            fg='green', bold=True) +
                " Waiting for new block for " +
                click.style(common.pp_duration(current_time - current_block_time), fg='white', bold=True) +
                ". " +
                click.style("(use Ctrl-C to stop)\r", fg='black'),
                nl=False
            )
            common.hide_cursor()
        time.sleep(delay)



@click.command()
@click.option("-d", "--duration",
              help="stop monitoring after given minutes",
              default=0,
              type=int)
@click.option("-D", "--delay", help="delay between blockchain request in seconds", default=2)
@click.option("-e", "--endpoint",
              help="Force com-chain endpoint")
@click.option("-r", "--raw", is_flag=True, help="Print raw values.")
def run(duration, delay, endpoint, raw):

    duration = duration * 60
    pyc3l = Pyc3l(endpoint)

    global pp_wait_block
    if not raw:
        pp_wait_block = common.protect_tty(pp_wait_block)

    blocks = []
    deltas = []
    start = time.time()
    pp_wait_block(pyc3l, duration, delay, raw, blocks, deltas)

    if raw:
        return
    msg = f"During the {common.pp_duration(time.time() - start)} run, "
    if blocks:
        msg += (
            f"{len(blocks)} blocks where added.\n" +
            textwrap.indent(f"Average delay for new block is {common.pp_duration(sum(deltas) / len(blocks))}", '  ')
        )
    else:
        msg += "no blocks where added."
    print(click.style(f"\r{now_str()}", fg='cyan') +
            click.style(" Ctrl-C catched ! Run ended.", fg='white', bold=True) + f" {msg}")


if __name__ == "__main__":
    run()