#!/usr/bin/env python


import click
from web3 import Web3


from pyc3l import Pyc3l


@click.command()
def run():
    pyc3l = Pyc3l()

    for endpoint in sorted(pyc3l.endpoints, key=lambda x: str(x)):
        print(f"endpoint: {endpoint}")

        pyc3l = Pyc3l(endpoint)
        tr_infos = pyc3l.getTrInfos("0x" + "0" * 40)

        print(f"  block: {pyc3l.getBlockNumber()}")
        print(f"  gasPrice: {Web3.fromWei(int(tr_infos['gasprice'], 16), 'gwei')} gwei")


if __name__ == "__main__":
    run()
