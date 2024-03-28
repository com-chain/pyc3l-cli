#!/usr/bin/env python


import click
import getpass
import time
import json

from pyc3l_cli import common
from pyc3l import Pyc3l



@click.command()
@click.option("-w", "--wallet-file", help="wallet path")
@click.option("-p", "--password-file", help="wallet password path")
@click.option("-d", "--json-data-file", help="JSON data path")
@click.option("-e", "--endpoint",
              help="Force com-chain endpoint.")
@click.argument("amount", type=float, required=False)
def run(wallet_file, password_file, json_data_file, endpoint, amount):

    pyc3l = Pyc3l(endpoint)

    wallet = pyc3l.Wallet.from_file(
        wallet_file or common.filepicker("Select Admin Wallet")
    )

    wallet.unlock(
        common.load_password(password_file) if password_file else getpass.getpass()
    )

    # open the list of account to process
    addresses = json.loads(
        common.file_get_contents(
            json_data_file
            or common.filepicker(
                "Select the file containing the list of accounts to process"
            )
        )
    )

    # get the amount to be pledged
    amount = amount or int(input("Amount to be pledged: "))

    print("------------- PROCESSING ------------------------")

    currency = wallet.currency
    for address in addresses:
        account = currency.Account(address)
        status = account.isActive
        print(f"Status of {address} is {status!r}")
        bal = account.GlobalBalance
        print(f"Balance of {address} is {bal}")
        total = amount - bal

        if total <= 0:
            continue

        pyc3l.registerCurrentBlock()

        wallet.enable(address)
        wallet.pledge(address, total)
        wallet.disable(address)

        print(" - done with " + address)

        while not pyc3l.hasChangedBlock():
            time.sleep(5)

    print("------------- END PROCESSING ------------------------")


if __name__ == "__main__":
    run()
