import time
import logging

logger = logging.getLogger(__name__)


def file_get_contents(filename):
    with open(filename, "r") as f:
        return f.read()


def readCSV(file_path):
    import csv

    with open(file_path, newline="") as csvfile:
        for record in csv.DictReader(csvfile):
            yield record


def filepicker(title):
    import tkinter.filedialog
    import tkinter as tk

    filename = tkinter.filedialog.askopenfilename(title=title)
    if not filename:
        raise Exception("Filepicker was canceled.")
    return filename


def load_wallet(filename):
    import json

    logger.info("Opening file %r", filename)
    wallet = json.loads(file_get_contents(filename))
    logger.info(
        "  File contains wallet with address 0x%s on server %r",
        wallet["address"],
        wallet["server"]["name"],
    )
    return wallet


def unlock_account(wallet, password):
    import json
    from eth_account import Account

    account = Account.privateKeyToAccount(Account.decrypt(wallet, password))
    logger.info("Account %s opened.", account.address)
    return account


def load_password(filename):
    import re

    password = file_get_contents(filename)
    password = re.sub(r"\r?\n?$", "", password)  ## remove ending newline if any
    return password


def pp_duration(seconds):
    """Pretty print a duration in seconds

    >>> pp_duration(30)
    '30s'
    >>> pp_duration(60)
    '01m00s'
    >>> pp_duration(3601)
    '01h00m01s'

    """

    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    return "".join(
        [
            ("%02dh" % h if h else ""),
            ("%02dm" % m if m or h else ""),
            ("%02ds" % s),
        ]
    )


def wait_for_transactions(api, transactions_hash, wait=5):
    print("Waiting for all transaction to be mined:")
    start = time.time()
    transactions_hash = transactions_hash.copy()
    while transactions_hash:
        for h, address in list(transactions_hash.items()):
            msg = f"  Transaction {h[0:8]} to {address[0:8]}"
            if api.getTransactionBLock(h) is not None:
                msg += " has been mined !"
                del transactions_hash[h]
            else:
                msg += " still not mined"
            print(f"{msg} ({pp_duration(time.time() - start)} elapsed)")
            time.sleep(wait)

    print("All transaction have been mined, bye!")
