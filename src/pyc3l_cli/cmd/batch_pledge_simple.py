#!/usr/bin/env python


import click
import getpass
import time
import json

from pyc3l_cli import common
from pyc3l.ApiHandling import ApiHandling
from pyc3l.ApiCommunication import ApiCommunication


@click.command()
@click.option("-w", "--wallet-file", help="wallet path")
@click.option("-p", "--password-file", help="wallet password path")
@click.option("-d", "--json-data-file", help="JSON data path")
@click.option("-e", "--endpoint",
              help="Force com-chain endpoint.")
@click.argument("amount", type=float, required=False)
def run(wallet_file, password_file, json_data_file, endpoint, amount):

    wallet_file = wallet_file or common.filepicker("Select admin wallet")
    wallet = common.load_wallet(wallet_file)

    password = (
        common.load_password(password_file) if password_file else getpass.getpass()
    )
    account = common.unlock_account(wallet, password)

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

    # load the high level functions
    api_com = ApiCommunication(wallet["server"]["name"], endpoint)

    print("------------- PROCESSING ------------------------")

    for address in addresses:
        status = api_com.getAccountStatus(address)
        print("Status of " + address + " is " + str(status))
        bal = api_com.getAccountGlobalBalance(address)
        print("Balance of " + address + " is " + str(bal))
        total = amount - bal

        if total > 0:
            api_com.lockUnlockAccount(account, address, lock=False)
            api_com.pledgeAccount(account, address, total)
            api_com.lockUnlockAccount(account, address, lock=True)

        print(" - done with " + address)

        # write the next block
        while not api_com.hasChangedBlock():
            time.sleep(5)

    print("------------- END PROCESSING ------------------------")


if __name__ == "__main__":
    run()
