#!/usr/bin/env python


import click
import getpass
import time
import json

from pyc3l_cli import common
from pyc3l.ApiHandling import ApiHandling
from pyc3l.ApiCommunication import ApiCommunication


@click.command()
@click.option("-w", "--wallet-file", help="wallet path")
@click.option("-p", "--password-file", help="wallet password path")
@click.option("-d", "--json-data-file", help="JSON data path")
@click.argument('amount', type=int, required=False)
def run(wallet_file, password_file, json_data_file, amount):

    # load API
    api_handling = ApiHandling()

    wallet_file = wallet_file or common.filepicker('Select Admin Wallet')
    wallet = common.load_wallet(wallet_file)

    password = common.load_password(password_file) if password_file else getpass.getpass()
    account = common.unlock_account(wallet, password)

    # open the list of account to process
    publics = json.loads(
        common.file_get_contents(
            json_data_file or
            common.filepicker("Select the file containing the list of accounts to process")
        )
    )

    # get the amount to be pledged
    amount  = amount or int(input("Amount to be pledged: "))

    #load the high level functions
    api_com = ApiCommunication(api_handling, wallet['server']['name'])
      
    
    print('------------- PROCESSING ------------------------')
    
    for public in publics:
        status = api_com.getAccountStatus(public)
        print('Status of '+public + ' is '+str(status))
        bal = api_com.getAccountGlobalBalance(public)
        print('Balance of '+public + ' is '+str(bal))
        total = amount - bal 
	
        if total>0:
            res, r = api_com.lockUnlockAccount(account, public, lock=False)
            res, r = api_com.pledgeAccount(account, public, total)
            res, r = api_com.lockUnlockAccount(account, public, lock=True)

        print(' - done with '+public)
        
        # write the next block
        while not api_com.hasChangedBlock():
            time.sleep( 5 )

    print('------------- END PROCESSING ------------------------')


if __name__ == "__main__":
    run()