#!/usr/bin/env python
"""Monitors block rate"""

import click
import pprint

from pyc3l import Pyc3l


@click.command()
@click.option("-e", "--endpoint",
              help="Force com-chain endpoint.")
@click.option("-c", "--currency",
              help="Force com-chain endpoint.",
              default="Lemanoplis")
@click.argument("transaction")
def run(endpoint, currency, transaction):

    # load the high level functions
    currency = Pyc3l(endpoint).Currency(currency)
    res = currency.getTransactionInfo(transaction)
    if isinstance(res, str):
        import json

        res = json.loads(res)

    pprint.pprint(res)
