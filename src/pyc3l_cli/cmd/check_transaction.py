#!/usr/bin/env python
"""Monitors block rate"""

import click
import pprint

from pyc3l import Pyc3l


@click.command()
@click.option("-e", "--endpoint",
              help="Force com-chain endpoint.")
@click.argument("transaction")
def run(endpoint, transaction):

    # load the high level functions
    transaction = Pyc3l(endpoint).Transaction(transaction)

    pprint.pprint(transaction.data)
