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
@click.argument("address_from", type=str, required=False)
@click.argument("address_to", type=str, required=False)
@click.argument("amount", type=float, required=False)
def run(wallet_file, password_file, endpoint, address_from, address_to, amount):

    pyc3l = Pyc3l(endpoint)

    wallet = pyc3l.Wallet.from_file(
        wallet_file or common.filepicker("Select Admin Wallet")
    )

    wallet.unlock(
        common.load_password(password_file) if password_file else getpass.getpass()
    )

    symbol = wallet.currency.symbol

    print(
        f"Wallet {wallet.address} global balance: " +
        f"{wallet.GlobalBalance} {symbol}"
    )

    lst = wallet.MyDelegations
    print(f"  We have {len(lst)} delegations")

    if len(lst) == 0:
        print("Error: No available delegations")
        exit(1)

    print("  MyDelegations:")
    for address, delegation_amount in lst.items():
        print(f"    - from {address} for {delegation_amount} {symbol}")

    print(wallet.transferOnBehalfOf(
        address_from, address_to, amount,
        message_from="pyc3l",
        message_to="pyc3l",
    ))


if __name__ == "__main__":
    run()
