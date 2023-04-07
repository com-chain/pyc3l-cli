import getpass

from pyc3l_cli import common
from pyc3l.ApiHandling import ApiHandling
from pyc3l.ApiCommunication import ApiCommunication

# Load the API
api_handling = ApiHandling()


wallet_file = common.filepicker('Select Admin Wallet')
wallet = common.load_wallet(wallet_file)

password = getpass.getpass()
account = common.unlock_account(wallet, password)


address_test_lock = '0xE00000000000000000000000000000000000000E'


#load the high level functions
api_com = ApiCommunication(api_handling, wallet['server']['name'])

status = api_com.getAccountStatus(address_test_lock)
print( 'Account '+address_test_lock+' is currently actif = ' + str(status))
print('Balance = '+str(api_com.getAccountGlobalBalance(address_test_lock)))


res, r = api_com.lockUnlockAccount(account, address_test_lock, lock=False)
print(res)
print(r.text)
print("")

res, r = api_com.pledgeAccount(account, address_test_lock, 0.01)
print(res)
print(r.text)
print("")

res, r = api_com.lockUnlockAccount(account, address_test_lock, lock=True)
print(res)
print(r.text)
print("")
