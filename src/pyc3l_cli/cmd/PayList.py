#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import click
import sys
import time
import getpass

from pyc3l.ApiHandling import ApiHandling
from pyc3l.ApiCommunication import ApiCommunication
from pyc3l_cli import common



@click.command()
@click.option("-w", "--wallet-file", help="wallet path")
@click.option("-p", "--password-file", help="wallet password path")
@click.option("-d", "--csv-data-file", help="CSV data path")
@click.option("-D", "--delay", help="delay between blockchain request", default=15)
@click.option("-y", "--no-confirm", help="Bypass confirmation and always assume 'yes'", is_flag=True)
def run(wallet_file, password_file, csv_data_file, delay, no_confirm):
    """Batch transfer using CSV file

    """

    ###############################################################################
    ## Parametrization
    ###############################################################################
    ## Columns in the CSV file
    address_column='Address'
    amount_column='Montant'
    message_to='Libellé envoyé'
    message_from='Libellé gardé'

    ###############################################################################

    def prepareTransactionData(header, data, address_column='Address',
                               amount_column='Montant',
                               message_to='Libellé envoyé',
                               message_from='Libellé gardé'):

        add_ind = header.index(address_column)
        ammount_ind = header.index(amount_column)
        m_to_ind = header.index(message_to)
        m_from_ind = header.index(message_from)


        prepared_transactions=[]
        total=0
        for row in data:
            prepared_transactions.append({'add':row[add_ind],'amount':float(row[ammount_ind]),'m_to':row[m_to_ind],'m_from':row[m_from_ind]})
            total+=prepared_transactions[-1]['amount']

        return prepared_transactions, total


    ################################################################################
    ##     (1) CSV file handling
    ################################################################################
    csv_data_file = csv_data_file or common.filepicker('Choose a CSV file')
    header, data=common.readCSV(csv_data_file)
    prepared_transactions, total = prepareTransactionData(header, data)

    print('The file "'+csv_data_file+'" has been read.')
    print('It contains '+str(len(prepared_transactions))+' transaction(s) for a total of '+str(total))

    if not no_confirm and not input('Continue to the execution (y/n)') == 'y':
        sys.exit()


    ################################################################################
    ##     (2) Load the account and check funds availability
    ################################################################################

    # Load the API
    api_handling = ApiHandling()

    wallet_file = wallet_file or common.filepicker('Select Admin Wallet')
    wallet = common.load_wallet(wallet_file)

    password = common.load_password(password_file) if password_file else getpass.getpass()
    account = common.unlock_account(wallet, password)

    #load the high level functions
    api_com = ApiCommunication(api_handling, wallet['server']['name'])

    CM_balance=api_com.getAccountCMBalance(account.address)
    CM_limit=api_com.getAccountCMLimitMinimum(account.address)
    Nant_balance = api_com.getAccountNantBalance(account.address)
    Sender_status = api_com.getAccountStatus(account.address)

    if Sender_status!=1:
        print("Error: The Sender Wallet is locked!")
        sys.exit()

    use_cm=False
    use_negative_cm=False
    use_nant=False
    use_mix=False

    if total<=CM_balance:
        use_cm=True
    elif total<=Nant_balance:
        use_nant=True
    elif total<=CM_balance-CM_limit:
        print("Warning: The Mutual credit balance of the Sender Wallet will be negative.")
        use_negative_cm=True
    else:
        print("Warning: Not enough fund for unsplited transactions")
        if total>CM_balance+CM_balance-CM_limit:
            print("Error: The Sender Wallet is underfunded: This batch of payment="+str(total)+" Nant balance="+str(Nant_balance)+" CM balance="+str(CM_balance)+" CM Limit="+str(CM_limit))
            sys.exit()
        else:
            use_mix=True


    ################################################################################
    ##     (3) Check target accounts are available
    ################################################################################

    total_cm=0
    total_nant=0
    for tran in prepared_transactions:
        target_address = tran['add']
        target_amount = tran['amount']

        target_status = api_com.getAccountStatus(target_address)
        if target_status!=1:
             print("Warning: The Target Wallet with address "+target_address+"is locked and will be skipped")
        else:
            tran['unlocked']=1
            if use_nant:
                total_nant+=target_amount
                tran['type']='N'
            else:
                CM_target_balance=api_com.getAccountCMBalance(target_address)
                CM_target_limit=api_com.getAccountCMLimitMaximum(target_address)
                tran['canCM'] = target_amount+CM_target_balance<CM_target_limit
                if  tran['canCM']:
                    total_cm+=target_amount
                    tran['type']='CM'
                else:
                    total_nant+=target_amount
                    tran['type']='N'
                    print("Warning: The Target Wallet with address "+target_address+" cannot accept "+str(target_amount)+ "in mutual credit (will try the nant.)")

    if  total_nant>Nant_balance or  total_cm>CM_balance-CM_limit:
        print("Error: Due to constraint on the target amount the splitting ("+str(total_nant)+"Nant + "+str(total_cm)+"CM) is not compatible with the available funds")
        sys.exit()          

    if not no_confirm and not input('Ready to send payments ? (y/n)') == 'y':
        sys.exit()

    ################################################################################
    ##     (4) Execute transactions
    ################################################################################
    transaction_hash={}
    for tran in prepared_transactions:
        if tran['unlocked']==1 and tran['type']=='N':
            res, r = api_com.transfertNant(account, tran['add'], tran['amount'], message_from=tran['m_from'], message_to=tran['m_to'])
            transaction_hash[res]=tran['add']
            print("Transaction Nant sent to "+tran['add'])
            time.sleep( delay ) # Delay for not overloading the BlockChain
        elif  tran['unlocked']==1 and tran['type']=='CM':
            res, r = api_com.transfertCM(account, tran['add'], tran['amount'], message_from=tran['m_from'], message_to=tran['m_to'])
            transaction_hash[res]=tran['add']
            print("Transaction CM sent to "+tran['add'])
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
    #    if api_com.getTransactionBLock(hash_to_test)!=None:
    #        print("Transaction to "+transaction_hash[hash_to_test] + " has been mined")
    #    else:
    #        time.sleep( 15 ) 

    #print("All transaction have been mined, bye!")

if __name__ == "__main__":
    run()

