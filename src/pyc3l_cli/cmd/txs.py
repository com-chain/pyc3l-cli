#!/usr/bin/env python

import click

from pyc3l_cli import common
from pyc3l import Pyc3l



@click.command()
@click.option("-e", "--endpoint", help="Force com-chain endpoint.")
@click.option("-n", "--count", help="Number of transactions to show", default=15)
@click.option("-r", "--raw", is_flag=True, help="Print raw values.")
@click.option("-c", "--currency", help="Show only transaction in given currency.")
@click.argument("address")
def run(endpoint, address, raw, count, currency):

    pyc3l = Pyc3l(endpoint)
    account = pyc3l.Account(address)
    first = True
    for idx, tx in enumerate(account.transactions):
        if idx >= count:
            break
        if currency and tx.currency.name != currency:
            continue
        if first:
            first = False
        else:
            if raw:
                print("---")
        print(common.pp_tx(tx, currency=currency is None, raw=raw), end="")


if __name__ == "__main__":
    run()
