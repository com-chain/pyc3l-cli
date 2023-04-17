#!/usr/bin/env python


import click
import getpass

from pyc3l_cli import common
from pyc3l import Pyc3l


@click.command()
@click.option("-w", "--wallet-file", help="wallet path")
@click.option("-p", "--password-file", help="wallet password path")
@click.option("-e", "--endpoint",
              help="Force com-chain endpoint.")
@click.argument("address", type=str, required=False)
@click.argument("amount", type=float, required=False)
def run(wallet_file, password_file, endpoint, address, amount):

    pyc3l = Pyc3l(endpoint)

    wallet = pyc3l.Wallet.from_file(
        wallet_file or common.filepicker("Select Admin Wallet")
    )

    wallet.unlock(
        common.load_password(password_file) if password_file else getpass.getpass()
    )

    currency = wallet.currency

    print(
        "The sender wallet "
        + wallet.address
        + ", on server "
        + currency._currency_name
        + " has a balance of = "
        + str(wallet.GlobalBalance)
    )

    res = wallet.delegate(
        address, amount
    )
    print(res)
    print("")


if __name__ == "__main__":
    run()
