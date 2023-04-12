#!/usr/bin/env python


import click
import sys
import time
import getpass

from pyc3l.ApiCommunication import ApiCommunication
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
    wallet_file = wallet_file or common.filepicker("Select Admin Wallet")
    wallet = common.load_wallet(wallet_file)

    password = (
        common.load_password(password_file) if password_file else getpass.getpass()
    )
    account = common.unlock_account(wallet, password)

    # load the high level functions
    print("INFO: load the high level functions.")
    api_com = ApiCommunication(wallet["server"]["name"], endpoint)

    print("INFO: Check the provided account to have admin role.")
    api_com.checkAdmin(account.address)
    status = api_com.getAccountStatus(account.address)

    if status != 1:
        print("Error: The Admin Wallet is locked!")
        sys.exit(1)

    ################################################################################
    ##     (3) Check target accounts are available
    ################################################################################

    transactions = map(
        lambda transaction: dict(
            transaction,
            unlocked=api_com.getAccountStatus(transaction["address"]) == 1
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

        res = api_com.pledgeAccount(
            account, t["address"], t["amount"], message_to=t["message"]
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
        common.wait_for_transactions(api_com, transaction_hash)



if __name__ == "__main__":
    run()
