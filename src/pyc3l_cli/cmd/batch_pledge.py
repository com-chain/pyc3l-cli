#!/usr/bin/env python


import click
import sys
import time
import getpass

from pyc3l import Pyc3l
from pyc3l_cli import common


@click.command()
@click.option("-w", "--wallet-file", help="wallet path")
@click.option("-p", "--password-file", help="wallet password path")
@click.option("-d", "--csv-data-file", help="CSV data path")
@click.option("-D", "--delay", help="delay between blockchain request", default=15)
@click.option("-e", "--endpoint",
              help="Force com-chain endpoint.")
@click.option("-W", "--wait", help="wait for integration in blockchain", is_flag=True)
@click.option(
    "-y",
    "--no-confirm",
    help="Bypass confirmation and always assume 'yes'",
    is_flag=True,
)
def run(wallet_file, password_file, csv_data_file, delay, endpoint, wait, no_confirm):
    """Batch pledging using CSV file"""

    ################################################################################
    ##     (1) CSV file handling
    ################################################################################
    csv_data_file = csv_data_file or common.filepicker("Choose a CSV file")
    transactions = list(map(
        lambda record: {
            "address": record["Address"],
            "amount": float(record["Montant"]),
            "message": record["Message"],
        },
        common.readCSV(csv_data_file)
    ))

    print(f'The file {csv_data_file!r} has been read.')
    print("It contains %s transaction(s) for a total of %s" % (
        len(transactions),
        sum(t["amount"] for t in transactions),
    ))

    if not no_confirm and not input("Continue to the execution (y/n)") == "y":
        sys.exit()

    ################################################################################
    ##     (2) Load the account and check funds availability
    ################################################################################

    # Load the API
    print("INFO: Load the API.")
    pyc3l = Pyc3l(endpoint)

    wallet = pyc3l.Wallet.from_file(
        wallet_file or common.filepicker("Select Admin Wallet")
    )

    wallet.unlock(
        common.load_password(password_file) if password_file else getpass.getpass()
    )

    print("INFO: Check the provided account to have admin role.")
    if not wallet.isValidAdmin:
        print("Error: The wallet's account is not admin")
        sys.exit(1)

    if not wallet.isActive:
        print("Error: The Admin Wallet is locked!")
        sys.exit(1)

    ################################################################################
    ##     (3) Check target accounts are available
    ################################################################################

    currency = wallet.currency
    transactions = map(
        lambda t: dict(
            t,
            unlocked=currency.Account(t["address"]).isActive
        ),
        transactions
    )

    if (not no_confirm and
        not input(
            f"Ready to pledge some {wallet['server']['name']} ? (y/n) "
        ) == "y"):
        sys.exit()

    ################################################################################
    ##     (4) Execute transactions
    ################################################################################
    transaction_hash = {}
    for t in transactions:
        if not t["unlocked"]:
            print(f"Transaction to {t['address']} skipped")
            continue

        res = wallet.pledge(
            t["address"], t["amount"], message_to=t["message"]
        )
        transaction_hash[res] = t["address"]
        print(
            "Transaction Nant sent to %s (%.2f LEM) with message %r Transaction Hash=%s" % (
                t["address"], t["amount"], t["message"], res,
            )
        )

        time.sleep(delay)  # Delay for not overloading the BlockChain


    print("All transaction have been sent!")

    if wait:
        common.wait_for_transactions(pyc3l, transaction_hash)



if __name__ == "__main__":
    run()
