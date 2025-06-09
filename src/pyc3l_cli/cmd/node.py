#!/usr/bin/env python

import click
import textwrap

from web3 import Web3

from pyc3l import Pyc3l, ApiHandling

from .. import common


DUMMY_ADDRESS = "0x" + "0" * 40


@click.command()
@click.option("-a", "--address", help="Address to check nonces.")
@click.option("-e", "--endpoint", help="Force com-chain endpoint.", default="all")
@click.option("-r", "--raw", is_flag=True, help="Print raw values.")
def run(address, endpoint, raw):
    address = address or DUMMY_ADDRESS
    pyc3l = Pyc3l()

    endpoints = []
    if endpoint == "all":
        endpoints = sorted(ApiHandling().endpoints, key=lambda x: str(x))
    elif endpoint:
        endpoints = [endpoint]
    else:
        endpoints = [None]  ## select a random one

    for endpoint in endpoints:
        pp_endpoint = str(endpoint)
        pp_endpoint = (
            pp_endpoint[8:] if pp_endpoint.startswith("https://") else pp_endpoint
        )
        if not raw:
            pp_endpoint = click.style(pp_endpoint, fg="bright_white", bold=True)

        print(pp_endpoint + ":")

        pyc3l = Pyc3l(endpoint)

        tr_infos = pyc3l.getTrInfos(address)
        if address != DUMMY_ADDRESS:
            print(f"  nonce: {int(tr_infos['nonce'], 16)}")
        print(f"  block: {pyc3l.getBlockNumber()}")
        print(f"  gasPrice: {Web3.fromWei(int(tr_infos['gasprice'], 16), 'gwei')} gwei")
        txpool = pyc3l.getTxPool()
        for label in ["pending", "queued"]:
            if len(txpool[label]):
                print("  %s:" % label)
                for add, txs in txpool[label].items():
                    print(f"    {common.pp_address(add, raw=raw)}:")
                    for nonce, bc_tx in txs.items():
                        bc_tx = pyc3l.BCTransaction(bc_tx["hash"], bc_tx)
                        msg = common.pp_bc_tx(bc_tx, raw=raw, exclude=['caller', 'status'])
                        if raw:
                            print(
                                "      %d:\n%s"
                                % (int(nonce), textwrap.indent(msg, " " * 8)),
                                end="",
                            )
                        else:
                            print("      %s %s"
                                  % (click.style("%5d" % int(nonce), fg='yellow'), msg), end="")
            else:
                if raw:
                    print("  %s: {}" % label)


if __name__ == "__main__":
    run()
