#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import click
import sys
import time
import tkinter
import re
import os.path

from pyc3l.ApiHandling import ApiHandling
from pyc3l.ApiCommunication import ApiCommunication
from pyc3l_cli.common import readCSV, file_get_contents
from pyc3l_cli.LocalAccountOpener import LocalAccountOpener


@click.command()
@click.option("-w", "--wallet-file", help="wallet path")
@click.option("-p", "--password-file", help="wallet password path")
@click.option("-d", "--csv-data-file", help="CSV data path")
@click.option("-D", "--delay", help="delay between blockchain request", default=15)
@click.option("-y", "--no-confirm", help="Bypass confirmation and always assume 'yes'", is_flag=True)
def run(wallet_file, password_file, csv_data_file, delay, no_confirm, *args, **kwargs):
    """Batch pledging using CSV file

    """

    ###############################################################################
    ## Parametrization
    ###############################################################################
    ## Columns in the CSV file
    address_column='Address'
    amount_column='Montant'
    message_column='Message'

    ###############################################################################

    def prepareTransactionData(header, data, address_column='Address',
                               amount_column='Montant', message_column='Message'):

        add_ind = header.index(address_column)
        ammount_ind = header.index(amount_column)
        message_ind = header.index(message_column)



        prepared_transactions=[]
        total=0
        for row in data:
            prepared_transactions.append({'add':row[add_ind],'amount':float(row[ammount_ind]),'message':row[message_ind]})
            total+=prepared_transactions[-1]['amount']

        return prepared_transactions, total


    ################################################################################
    ##     (1) CSV file handling
    ################################################################################
    if not csv_data_file:
        csv_data_file = tkinter.filedialog.askopenfilename(title='Choose a CSV file')
        if not csv_data_file:
            exit(1)
    header, data=readCSV(csv_data_file)
    prepared_transactions, total = prepareTransactionData(header, data)

    print('The file "'+csv_data_file+'" has been read.')
    print('It contains '+str(len(prepared_transactions))+' transaction(s) for a total of '+str(total))

    if not no_confirm and not input('Continue to the execution (y/n)')=='y':
        sys.exit()


    ################################################################################
    ##     (2) Load the account and check funds availability
    ################################################################################

    # Load the API
    print('INFO: Load the API.')
    api_handling = ApiHandling()

    password = None
    if password_file:
        if not os.path.exists(password_file):
            click.echo("%s: %s" % (
                click.style("Error", fg='red', bold=True),
                f"Error: Provided password file {password_file!r} doesn't exist"
            ))
            exit(1)
        password = file_get_contents(password_file)
        password = re.sub(r'\r?\n?$', '', password)  ## remove ending newline if any

    account_opener = LocalAccountOpener()
    server, sender_account = account_opener.openAccountInteractively(
        'Select Admin Wallet',
        account_file=wallet_file,
        password=password
    )

    #load the high level functions
    print('INFO: load the high level functions.')
    api_com = ApiCommunication(api_handling, server)


    print('INFO: Check the provided account to have admin role.')
    api_com.checkAdmin(sender_account.address)
    Sender_status = api_com.getAccountStatus(sender_account.address)

    if Sender_status!=1:
        print("Error: The Admin Wallet is locked!")
        sys.exit()




    ################################################################################
    ##     (3) Check target accounts are available
    ################################################################################

    print('INFO: Check the targets accounts are not locked.')
    for tran in prepared_transactions:
        target_address = tran['add']

        target_status = api_com.getAccountStatus(target_address)
        if target_status!=1:
            print("Warning: The Target Wallet with address "+target_address+"is locked and will be skipped")
            tran['unlocked']=0
        else:
            tran['unlocked']=1

    if not no_confirm and not input(f'Ready to pledge some {server} ? (y/n) ') == 'y':
        sys.exit()

    ################################################################################
    ##     (4) Execute transactions
    ################################################################################
    transaction_hash={}
    for tran in prepared_transactions:
        if tran['unlocked']==1:
            res, r = api_com.pledgeAccount(sender_account, tran['add'], tran['amount'], message_to=tran['message']) 
            transaction_hash[res]=tran['add']
            print("Transaction Nant sent to "+tran['add'] + ' ('+str(tran['amount'])+'LEM) with message "'+tran['message']+'" Transaction Hash='+ res)

            time.sleep( delay ) # Delay for not overloading the BlockChain

        else :
            print("Transaction to "+tran['add'] + " skipped")

    print("All transaction have been send, bye!")

    ################################################################################
    ##     (5) Wait for confirmation
    ################################################################################
    #
    #while len(transaction_hash)>0:
    #    hash_to_test = list(transaction_hash.keys())[0] 
    #    if api_com.getTransactionBlock(hash_to_test)!=None:
    #        print("Transaction to "+transaction_hash[hash_to_test] + " has been mined")
    #    else:
    #        time.sleep( 15 ) 

    #print("All transaction have been mined, bye!")

if __name__ == "__main__":
    run()
