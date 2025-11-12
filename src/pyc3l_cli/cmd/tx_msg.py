#!/usr/bin/env python

import json
import click

from pyc3l_cli import common
from pyc3l import Pyc3l


@click.command()
@click.option("-e", "--endpoint", help="Force com-chain endpoint.")
@click.option("-n", "--count", help="Number of transactions to show", default=15)
@click.option("-r", "--raw", is_flag=True, help="Print raw values.")
@click.option("-c", "--currency", help="Show only transaction in given currency.")
@click.argument("address")
@click.argument("message_key")
def run(endpoint, address, raw, count, currency, message_key):

    pyc3l = Pyc3l(endpoint)
    account = pyc3l.Account(address)
    idx = 0

    for tx in account.transactions:
        if currency and tx.currency.name != currency:
            continue
        if int(tx.direction) != 2 or tx.pending:
            continue
        idx += 1
        if idx > count:
            break

        crypted_msg = tx.message_to
        msg, _key = tx.currency.decryptTransactionMessage(
            crypted_msg,
            private_message_key=message_key
        )
        data = {
            "hash": tx.hash,
            "time": tx.time_ts,
            "amount": f"{float(tx.sent) / 100:.2f}",
            "msg": msg,
        }
        print(json.dumps(data))


if __name__ == "__main__":
    run()
