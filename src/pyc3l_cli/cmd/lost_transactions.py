#!/usr/bin/env python

import click
import collections

from pyc3l_cli import common
from pyc3l import Pyc3l

import time

def line_count(file_path):
    with open(file_path, 'r') as file:
        return sum(1 for _ in file)


@click.command()
@click.option("-d", "--csv-data-file", help="CSV data path")
@click.option("-e", "--endpoint", help="Force com-chain endpoint.")
def run(csv_data_file, endpoint):
    pyc3l = Pyc3l(endpoint)

    csv_data_file = csv_data_file or common.filepicker("Choose a CSV file")
    lc = line_count(csv_data_file)
    print(f'Total number of accounts: {lc}')

    rows = common.readCSV(csv_data_file)

    reports = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    start = time.time()
    for idx, row in enumerate(rows):
        currency = row['currency']
        address = row['address']
        try:
            data = pyc3l.endpoint.lost_transactions.get(params={'addr': address})
            reports[currency]['done'].append(address)
            reports[currency]['lost'].extend(data['pending_and_rejected'])
        except Exception as e:
            print(f"Failed to get lost transactions for {address} on {currency}")
            reports[currency]['failed'].append(address)
        now = time.time()
        if now - start > 5:
            start = now
            print(f'{100 * idx / lc:.2f}% processed...')

    for currency, report in reports.items():
        print(f'Currency: {currency}')
        print(f'  # Accounts in error status: {len(report["failed"])}')
        for address in report['failed']:
            print(f'    - {address}')
        print(f'  # Accounts successfully read: {len(report["done"])}')
        print(f'  # Pending and rejected transactions: {len(report["lost"])}')

        w_list = collections.defaultdict(int)
        for error in report["lost"]:
            w_list[error['add1']] += 1
            w_list[error['add2']] += 1

        for address, count in sorted(w_list.items(), key=lambda x: x[1], reverse=True):
            if address != 'Admin':
                print(f'    - {address} appears in {count} transaction pending or failed.')
            else:
                print(f'    - {count} pledges are pending or failed.')

        print('')

if __name__ == "__main__":
    run()
