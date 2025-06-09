#!/usr/bin/env python

import datetime
import click

from pyc3l import Pyc3l
from pyc3l_cli import common

@click.command()
@click.option("-e", "--endpoint", help="Force com-chain endpoint.")
@click.option("-r", "--raw", is_flag=True, help="Print raw values.")
@click.option("-n", "--nb-txs", help="Number of transactions to show")
@click.argument("currency")
@click.argument("address")
def run(endpoint, currency, address, raw, nb_txs):
    pyc3l = Pyc3l(endpoint)

    nb_txs = int(nb_txs) if nb_txs else 10

    currency = pyc3l.Currency(currency)
    account = currency.Account(address)
    print(common.pp_account(account, raw, nb_tx=nb_txs))


if __name__ == "__main__":
    run()
