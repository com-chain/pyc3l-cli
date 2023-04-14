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

    address_test_lock = "0xE00000000000000000000000000000000000000E"

    currency = wallet.currency

    account_test_lock = currency.Account(address_test_lock)
    status = account_test_lock.Status
    print("Account " + address_test_lock + " is currently actif = " + str(status))
    print("Balance = " + str(account_test_lock.GlobalBalance))

    res = wallet.lockUnlockAccount(address_test_lock, lock=False)
    print(res)
    print("")

    res = wallet.pledgeAccount(address_test_lock, 0.01)
    print(res)
    print("")

    res = wallet.lockUnlockAccount(address_test_lock, lock=True)
    print(res)
    print("")


if __name__ == "__main__":
    run()
