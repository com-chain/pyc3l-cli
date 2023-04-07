#!/usr/bin/env python


import click
import getpass

from pyc3l_cli import common
from pyc3l.ApiHandling import ApiHandling
from pyc3l.ApiCommunication import ApiCommunication


@click.command()
@click.option("-w", "--wallet-file", help="wallet path")
@click.option("-p", "--password-file", help="wallet password path")
def run(wallet_file, password_file):

    # Load the API
    api_handling = ApiHandling()

    wallet_file = wallet_file or common.filepicker("Select Admin Wallet")
    wallet = common.load_wallet(wallet_file)

    password = (
        common.load_password(password_file) if password_file else getpass.getpass()
    )
    account = common.unlock_account(wallet, password)

    target_address = "0xE00000000000000000000000000000000000000E"

    # load the high level functions
    api_com = ApiCommunication(api_handling, wallet["server"]["name"])

    print(
        "The sender wallet "
        + account.address
        + ", on server "
        + wallet["server"]["name"]
        + " has a balance of = "
        + str(api_com.getAccountGlobalBalance(account.address))
    )

    res, r = api_com.transfertNant(
        account, target_address, 0.01, message_from="test", message_to="test"
    )
    print(res)
    print(r.text)
    print("")


if __name__ == "__main__":
    run()