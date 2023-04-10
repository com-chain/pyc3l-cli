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
