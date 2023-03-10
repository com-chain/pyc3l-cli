#!/usr/bin/python3
from pyc3l_cli.LocalAccountOpener import LocalAccountOpener
from pyc3l.ApiHandling import ApiHandling
from pyc3l.ApiCommunication import ApiCommunication

import time

# load the account list to be processed
def openKeyListFile():
    file_path = filedialog.askopenfilename(title = "Select the file containing the list of accounts to process")
    file_list = open(file_path, 'r') 
    file_content = file_list.read() 
    key_list = json.loads(file_content)
    return key_list


def main():

    # load API
    api_handling = ApiHandling()
    # refresh the node list
    api_handling.updateNodeRepo()

    # open the admin account
    account_opener = LocalAccountOpener()
    server, admin_account = account_opener.openAccountInteractively('open admin account',account_file='')

    # open the list of account to process
    publics = openKeyListFile()

    # get the amount to be pledged
    amount  = int(input("Amount to be pledged: "))
      
    # load the high level functions
    api_com = ApiCommunication(api_handling, server)
    
    print('------------- PROCESSING ------------------------')
    
    for public in publics:
        status = api_com.getAccountStatus(public)
        print('Status of '+public + ' is '+str(status))
        bal = api_com.getAccountGlobalBalance(public)
        print('Balance of '+public + ' is '+str(bal))
        total = amount - bal 
	
        if total>0:
            res, r = api_com.lockUnlockAccount(admin_account, public, lock=False)
            
            res, r = api_com.pledgeAccount(admin_account, public, total)
            
            res, r = api_com.lockUnlockAccount(admin_account, public, lock=True)

        print(' - done with '+public)
        
        # write the next block
        while not api_com.hasChangedBlock():
            time.sleep( 5 )

    print('------------- END PROCESSING ------------------------')
main()
