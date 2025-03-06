#!/usr/bin/env python
"""Monitors block rate"""

import click
import pprint
import textwrap
import json
import yaml


from .. import common

from pyc3l import Pyc3l, ApiHandling


@click.command()
@click.option("-e", "--endpoint", help="Force com-chain endpoint.")
@click.option("-r", "--raw", is_flag=True, help="Print raw values.")
@click.argument("transaction")
def run(endpoint, raw, transaction):
    endpoints = []
    if endpoint == "all":
        endpoints = sorted(ApiHandling().endpoints, key=lambda x: str(x))
    elif endpoint:
        endpoints = [endpoint]
    else:
        endpoints = [None]  ## select a random one

    for endpoint in endpoints:
        if len(endpoints) > 1:
            ## remove 'https://' prefix from endpoint if present
            pp_endpoint = str(endpoint)
            pp_endpoint = (
                pp_endpoint[8:] if pp_endpoint.startswith("https://") else pp_endpoint
            )
            if not raw:
                pp_endpoint = click.style(pp_endpoint, fg="bright_white", bold=True)
            print(pp_endpoint + ":")
        pyc3l = Pyc3l(endpoint)
        tx = pyc3l.Transaction(transaction)
        pp_tx = common.pp_tx(tx, currency=True, raw=raw)
        if pp_tx == "":
            continue
        if len(endpoints) > 1:
            pp_tx = textwrap.indent(pp_tx, "  ")
        print(pp_tx, end="")
        if raw:
            ## tx.data is in json, lets output yaml version
            tx_data_yml = "api-raw-data:\n" + textwrap.indent(
                yaml.dump(tx.data, default_flow_style=False, sort_keys=False), "  "
            )
            if len(endpoints) > 1:
                tx_data_yml = textwrap.indent(tx_data_yml, "  ")
            print(tx_data_yml, end="")
