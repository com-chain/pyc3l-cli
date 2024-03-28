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
def run(wallet_file, password_file, endpoint):

    pyc3l = Pyc3l(endpoint)

    wallet = pyc3l.Wallet.from_file(
        wallet_file or common.filepicker("Select Admin Wallet")
    )

    wallet.unlock(
        common.load_password(password_file) if password_file else getpass.getpass()
    )

    address_test = "0xE00000000000000000000000000000000000000E"

    currency = wallet.currency

    account = currency.Account(address_test)
    print(f"Account {address_test} is currently active = {account.isActive!r}")
    print("Balance = " + str(account.globalBalance))

    print(wallet.enable(address_test))
    print(wallet.pledge(address_test, 0.01))
    print(wallet.disable(address_test))


if __name__ == "__main__":
    run()
