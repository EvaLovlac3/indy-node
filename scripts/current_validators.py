#!/usr/bin/python3

import string
import json
import csv
import logging
from logging.handlers import RotatingFileHandler
import argparse
import subprocess
import sys
import collections
import getpass

log_formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
logFile = 'current_validators.log'
my_handler = RotatingFileHandler(logFile, mode='a', maxBytes=1024 * 1024,
                                 backupCount=1, encoding=None, delay=0)
my_handler.setFormatter(log_formatter)
my_handler.setLevel(logging.INFO)
log = logging.getLogger('root')
log.setLevel(logging.INFO)
log.addHandler(my_handler)


def parse_transactions(ledger, protocol_version):
    log.info('Parsing ledger transactions into dictionary')

    validators = collections.OrderedDict()
    # validators is dictionary of dictionaries that maps dest to the current values of the attritubes for that dest
    #  { dest1:{'alias':value1, 'blskey':value1, ...} , dest2:{'alias':value2, 'blskey':value2, ...}, ...}

    for lLine in ledger:
        txn_json_dump = json.loads(lLine)

        if protocol_version == '1':
            if txn_json_dump[1]['dest'] is None:
                continue
            # Get destination field from the JSON dump of the current transaction
            current_dest = txn_json_dump[1]['dest']
            data_json_dump = txn_json_dump[1]['data']
            identifier = txn_json_dump[1]['identifier']
        elif protocol_version == '2':
            if txn_json_dump['txn']['data']['dest'] is None:
                continue
            current_dest = txn_json_dump['txn']['data']['dest']
            data_json_dump = txn_json_dump['txn']['data']['data']
            identifier = txn_json_dump['txn']['metadata']['from']
        else:
            log.error("please use a proper protocolVersion")
            return 1

        # Add destination to the dictionary if it does not exist
        if not (current_dest in validators.keys()):
            validators[current_dest] = {}

        # Update attribute value of the destination if the attributes exists in the current transaction dump
        try:
            validators[current_dest]['alias'] = data_json_dump['alias']
        except KeyError:
            pass
        try:
            validators[current_dest]['blskey'] = data_json_dump['blskey']
        except KeyError:
            pass
        try:
            validators[current_dest]['client_ip'] = data_json_dump['client_ip']
        except KeyError:
            pass
        try:
            validators[current_dest]['client_port'] = data_json_dump['client_port']
        except KeyError:
            pass
        try:
            validators[current_dest]['node_ip'] = data_json_dump['node_ip']
        except KeyError:
            pass
        try:
            validators[current_dest]['node_port'] = data_json_dump['node_port']
        except KeyError:
            pass
        try:
            validators[current_dest]['services'] = data_json_dump['services']
        except KeyError:
            pass
        if 'identifier' not in validators[current_dest]:
            try:
                validators[current_dest]['identifier'] = identifier
            except KeyError:
                pass
        validators[current_dest]['dest'] = current_dest

    return validators


def get_ledger():
    prefix = ['/usr/bin/sudo', '-i', '-u', 'indy']
    suffix = ['/usr/local/bin/read_ledger', '--type', 'pool', '--count']
    if (getpass.getuser() != 'indy'):
        command = prefix + suffix
    else:
        command = suffix
    try:
        completed = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE)
    except subprocess.CalledProcessError as err:
        log.error('attempting to run read_ledger --count subprocess: {}'.format(err))
        raise
    transCount = completed.stdout.decode('utf-8').strip()
    log.info('{} entries in ledger.'.format(transCount))
    suffix = ['/usr/local/bin/read_ledger', '--type', 'pool', '--frm', '1', '--to', completed.stdout]
    if getpass.getuser() != 'indy':
        command = prefix + suffix
    else:
        command = suffix
    try:
        completed = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE)
    except subprocess.CalledProcessError as err:
        log.error('attempting to run read_ledger subprocess to capture ledger data: {}'.format(err))
        raise
    ledgerLines = completed.stdout.decode('utf-8').splitlines()
    log.info('{} ledger entries received.'.format(len(ledgerLines)))
    return ledgerLines


def write_result(jsonOut):
    if jsonOut:
        log.info('Serializing info on validators to json')
        count = len(validators)
        print('[', end='')
        for i in validators.keys():
            print(json.dumps(validators[i], sort_keys=True), end='')
            if count > 1:
                print(',', end='')
                count -= 1
        print(']')
    else:
        log.info('Serializing info on validators to csv')
        fieldnames = ['alias', 'blskey', 'client_ip', 'client_port', 'node_ip', 'node_port', 'services', 'dest',
                      'identifier']
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        for i in validators.keys():
            writer.writerow(validators[i])
    return 0


def parse_inputs():
    parser = argparse.ArgumentParser(
        description='This script may be run on a validator node to discover information on all the validators '
                    'configured in the ledger.')

    parser.add_argument('--writeJson',
                        help='Boolean flag.  If set, the output is json. (Default: the output is csv.)',
                        action='set_true')

    parser.add_argument('--protocolVersion', help='Ledger protocol version. legacy = 1, current = 2, the default is set to 2'
                                                  'EXAMPLE: --protocolVersion 1')

    args = parser.parse_args()

    if not args.protocolVersion:
        args.protocolVersion = '2'  # Mike said leave this on protocol version 2
    elif args.protocolVersion == '1' or args.protocolVersion == '2':
        args.protocolVersion
    else:
        log.error("INVALID PARAMS \nPlease enter a correct parameter"
                  "\n EXAMPLE: protocolVersion 1")

    return args


if __name__ == '__main__':
    returned_args = parse_inputs()
    ledger = get_ledger()
    validators = parse_transactions(ledger, returned_args.protocolVersion)
    writeResult = write_result(returned_args.writeJson)
