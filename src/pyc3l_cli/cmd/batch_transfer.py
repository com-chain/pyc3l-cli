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
@click.option("-W", "--wait", help="wait for integration in blockchain", is_flag=True)
@click.option("-e", "--endpoint",
              help="Force com-chain endpoint.")
@click.option(
    "-y",
    "--no-confirm",
    help="Bypass confirmation and always assume 'yes'",
    is_flag=True,
)
def run(wallet_file, password_file, csv_data_file, delay, wait, endpoint, no_confirm):
    """Batch transfer using CSV file"""

    ################################################################################
    ##     (1) CSV file handling
    ################################################################################
    csv_data_file = csv_data_file or common.filepicker("Choose a CSV file")

    try:
        transactions = list(map(
            lambda r: {
                "address": r["Addresse"],
                "amount": float(r["Montant"]),
                "message_to": r["Libellé envoyé"],
                "message_from": r["Libellé gardé"],
            },
            common.readCSV(csv_data_file)
        ))
    except KeyError as e:
        print(f"Error: column {e.args[0]!r} not found in given CSV file.")
        sys.exit(1)

    total = sum(t["amount"] for t in transactions)
    print(f'The file {csv_data_file!r} has been read.')
    print("It contains %s transaction(s) for a total of %s" % (
        len(transactions),
        total,
    ))

    if not no_confirm and not input("Continue to the execution (y/n)") == "y":
        sys.exit()

    ################################################################################
    ##     (2) Load the account and check funds availability
    ################################################################################

    wallet_file = wallet_file or common.filepicker("Select Admin Wallet")
    wallet = common.load_wallet(wallet_file)

    password = (
        common.load_password(password_file) if password_file else getpass.getpass()
    )
    account = common.unlock_account(wallet, password)

    # load the high level functions
    api_com = ApiCommunication(wallet["server"]["name"], endpoint)

    CM_balance = api_com.getAccountCMBalance(account.address)
    CM_limit = api_com.getAccountCMLimitMinimum(account.address)
    Nant_balance = api_com.getAccountNantBalance(account.address)
    Sender_status = api_com.getAccountStatus(account.address)

    if Sender_status != 1:
        print("Error: The Sender Wallet is locked!")
        sys.exit()

    use_cm = False
    use_negative_cm = False
    use_nant = False
    use_mix = False

    if total <= CM_balance:
        use_cm = True
    elif total <= Nant_balance:
        use_nant = True
    elif total <= CM_balance - CM_limit:
        print(
            "Warning: The Mutual credit balance of the Sender Wallet will be negative."
        )
        use_negative_cm = True
    else:
        print("Warning: Not enough fund for unsplited transactions")
        if total > CM_balance + CM_balance - CM_limit:
            print(
                "Error: The Sender Wallet is underfunded: " +
                f"This batch of payment={total} Nant balance={Nant_balance}" +
                f"CM balance={CM_balance} CM Limit={CM_limit}"
            )
            sys.exit(1)
        else:
            use_mix = True

    ################################################################################
    ##     (3) Check target accounts are available
    ################################################################################

    total_cm = 0
    total_nant = 0
    for t in transactions:
        target_status = api_com.getAccountStatus(t['address'])
        if target_status != 1:
            print(
                "Warning: The Target Wallet with address "
                + t['address']
                + "is locked and will be skipped"
            )
            continue
        t["unlocked"] = 1
        if use_nant:
            total_nant += t['amount']
            t["type"] = "Nant"
            continue

        CM_target_balance = api_com.getAccountCMBalance(t['address'])
        CM_target_limit = api_com.getAccountCMLimitMaximum(t['address'])
        if t['amount'] + CM_target_balance < CM_target_limit:
            total_cm += t['amount']
            t["type"] = "CM"
            continue

        total_nant += t['amount']
        t["type"] = "Nant"
        print(
            "Warning: The Target Wallet with address "
            + t['address']
            + " cannot accept "
            + str(t['amount'])
            + "in mutual credit (will try the nant.)"
        )

    if total_nant > Nant_balance or total_cm > CM_balance - CM_limit:
        print(
            "Error: Due to constraint on the target amount the splitting " +
            f"({total_nant} Nant + {total_cm} CM)" +
            "is not compatible with the available funds"
        )
        sys.exit(1)

    if not no_confirm and not input("Ready to send payments ? (y/n)") == "y":
        sys.exit()

    ################################################################################
    ##     (4) Execute transactions
    ################################################################################

    transaction_hash = {}
    for t in transactions:
        if t["unlocked"] != 1:
            print(f"Transaction to {t['address']} skipped")
            continue
        res = getattr(api_com, f"transfert{t['type']}")(
            account,
            t["address"],
            t["amount"],
            message_from=t["message_from"],
            message_to=t["message_to"],
        )

        transaction_hash[res] = t["address"]
        print(f"Transaction {t['type']} sent to {t['address']}")
        time.sleep(delay)  # Delay for not overloading the BlockChain


    print("All transaction have been sent, bye!")

    ################################################################################
    ##     (5) Wait for confirmation
    ################################################################################

    if not wait:
        return

    print("Waiting for all transaction to be mined:")
    start = time.time()
    while transaction_hash:
        for h, address in list(transaction_hash.items()):
            msg = f"  Transaction {h[0:8]} to {address[0:8]}"
            if api_com.getTransactionBLock(h) is not None:
                msg += " has been mined !"
                del transaction_hash[h]
            else:
                msg += " still not mined"
            print(f"{msg} ({common.pp_duration(time.time() - start)} elapsed)")
            time.sleep(5)

    print("All transaction have been mined, bye!")


if __name__ == "__main__":
    run()
