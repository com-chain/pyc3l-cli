#!/usr/bin/env python

import datetime
import click
import getpass
from web3 import Web3


from pyc3l_cli import common
from pyc3l import Pyc3l


@click.command()
@click.option("-w", "--wallet-file", help="wallet path")
@click.option("-p", "--password-file", help="wallet password path")
@click.option("-e", "--endpoint", help="Force com-chain endpoint.")
def run(wallet_file, password_file, endpoint):
    pyc3l = Pyc3l(endpoint)

    wallet = pyc3l.Wallet.from_file(
        wallet_file or common.filepicker("Select Admin Wallet")
    )

    wallet.unlock(
        common.load_password(password_file) if password_file else getpass.getpass()
    )

    currency = wallet.currency
    print("Wallet %s:" % (wallet.address))

    account = wallet.account
    msgs = []
    for label in ["isActive", "isOwner", "type"]:
        msgs.append(f"{label} = {getattr(account, label)}")
    print(f"  {', '.join(msgs)}")
    print(f"  Balance: {account.globalBalance:10.2f} {currency.symbol}")
    print(f"    Nant : {account.nantBalance:10.2f} {currency.symbol}")
    print(
        f"    CM   : {account.cmBalance:10.2f} {currency.symbol} "
        f"({account.cmLimitMin} to {account.cmLimitMax} {currency.symbol})"
    )
    wei = int(account.EthBalance)
    print(f"  ETH balance = {wei} Wei (={Web3.fromWei(wei, 'ether')} Ether)")

    for label in [
        "Allowances",
        "Requests",
        "MyRequests",
        "Delegations",
        "MyDelegations",
        "AcceptedRequests",
        "RejectedRequests",
    ]:
        lst = getattr(account, label)
        if len(lst) == 0:
            continue
        print(f"  {label}:")
        for address, amount in lst.items():
            print(f"    - from {address} for {amount} {currency.symbol}")

    print("  Last transactions:")
    for tx in account.transactions:
        status, sent, direction, add1, add2, time, receivedat = (
            "mined" if tx["status"] == 0 else "pending",
            tx["sent"],
            tx["direction"],
            tx["add1"].lstrip("0x"),
            tx["add2"].lstrip("0x"),
            datetime.datetime.utcfromtimestamp(int(tx["time"])).isoformat(),
            datetime.datetime.utcfromtimestamp(int(tx["receivedat"])).isoformat(),
        )

        if direction == 1:
            src = add1[:6]
            dst = add2[:6]
            sign = "-"
        else:
            src = add2[:6]
            dst = add1[:6]
            sign = "+"

        sent_formatted = f"{sign}{float(sent) / 100:.2f}"
        block_info = f"  (req: {receivedat}, block: {tx['block']})"
        print(
            f"    {time.replace('T', ' ')}  {status:8s}  "
            f"{src} --> {dst} {sent_formatted:>7}"
            + (block_info if status == "mined" else "")
        )


if __name__ == "__main__":
    run()
