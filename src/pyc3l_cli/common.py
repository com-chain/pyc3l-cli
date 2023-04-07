
import csv
import logging

logger = logging.getLogger(__name__)


def file_get_contents(filename):
    with open(filename, 'r') as f:
        return f.read()


def readCSV(file_path):
    header=[]
    data=[]

    with open(file_path) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0
        length=0
        for row in csv_reader:

            if line_count == 0:
                length=len(row)
                header=[item.replace('"','').strip() for item in row]
            else:
                if len(row)>length:
                    new_row=[]
                    in_str=False
                    for item in row:

                        if not in_str:
                            new_row.append(item)
                            if item.count('"')==1:
                                in_str=True
                        else:
                            new_row[-1]= new_row[-1] + ','+item
                            if item.count('"')==1:
                                    in_str=False
                    row=new_row

                row = [item.replace('"','').strip() for item in row]
                data.append(row)
            line_count += 1
    return header, data


def filepicker(title):
    import tkinter.filedialog
    import tkinter as tk
    filename = tkinter.filedialog.askopenfilename(title=title)
    if not filename:
        raise Exception("Filepicker was canceled.")
    return filename

def load_wallet(filename):
    import json
    logger.info('Opening file %r', filename)
    wallet = json.loads(file_get_contents(filename))
    logger.info(
        '  File contains wallet with address 0x%s on server %r',
        wallet['address'],
        wallet['server']['name']
    )
    return wallet

def unlock_account(wallet, password):
    import json
    from eth_account import Account
    account = Account.privateKeyToAccount(
        Account.decrypt(wallet, password)
    )
    logger.info("Account %s opened.", account.address)
    return account

def load_password(filename):
    import re
    password = file_get_contents(filename)
    password = re.sub(r'\r?\n?$', '', password)  ## remove ending newline if any
    return password

