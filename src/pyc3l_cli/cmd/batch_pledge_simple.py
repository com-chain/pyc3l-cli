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
        status = account.Status
        print("Status of " + address + " is " + str(status))
        bal = account.GlobalBalance
        print("Balance of " + address + " is " + str(bal))
        total = amount - bal

        if total > 0:
            wallet.lockUnlockAccount(address, lock=False)
            wallet.pledgeAccount(address, total)
            wallet.lockUnlockAccount(address, lock=True)

        print(" - done with " + address)

        # write the next block
        while not currency.hasChangedBlock():
            time.sleep(5)

    print("------------- END PROCESSING ------------------------")


if __name__ == "__main__":
    run()
