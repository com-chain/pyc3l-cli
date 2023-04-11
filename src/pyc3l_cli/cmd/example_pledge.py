#!/usr/bin/env python


import click
import getpass

from pyc3l_cli import common
from pyc3l.ApiCommunication import ApiCommunication


@click.command()
@click.option("-w", "--wallet-file", help="wallet path")
@click.option("-p", "--password-file", help="wallet password path")
@click.option("-e", "--endpoint",
              help="Force com-chain endpoint.")
def run(wallet_file, password_file, endpoint):

    wallet_file = wallet_file or common.filepicker("Select Admin Wallet")
    wallet = common.load_wallet(wallet_file)

    password = (
        common.load_password(password_file) if password_file else getpass.getpass()
    )
    account = common.unlock_account(wallet, password)

    address_test_lock = "0xE00000000000000000000000000000000000000E"

    # load the high level functions
    api_com = ApiCommunication(wallet["server"]["name"], endpoint)

    status = api_com.getAccountStatus(address_test_lock)
    print("Account " + address_test_lock + " is currently actif = " + str(status))
    print("Balance = " + str(api_com.getAccountGlobalBalance(address_test_lock)))

    res = api_com.lockUnlockAccount(account, address_test_lock, lock=False)
    print(res)
    print("")

    res = api_com.pledgeAccount(account, address_test_lock, 0.01)
    print(res)
    print("")

    res = api_com.lockUnlockAccount(account, address_test_lock, lock=True)
    print(res)
    print("")


if __name__ == "__main__":
    run()
