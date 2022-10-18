import time
import sys
import logging
logging.Formatter.converter = time.gmtime
logging.basicConfig(
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/main_full_log.log"),
    ],
    format='%(asctime)s : %(levelname)s :  %(name)s  : %(funcName)s : %(message)s',
    level=logging.INFO
)
import pymongo
from web3 import Web3
from evaluation.evaluator import Evaluator
import evaluation.evaluation_config
import pandas as pd
import csv
import json
from collector import token_collector
from dotenv import load_dotenv
import indicators.liquidity
import indicators.holders
import os

load_dotenv(".env")

logger = logging.getLogger(__name__)

db_client = pymongo.MongoClient(os.getenv('MONGODB_INSTANCE'))
scam_db = db_client["eth-scam-checker"]


def change_scam_criteria(dataset):
    dataset_db = scam_db['dataset_collection']
    bugged_tokens_db = scam_db['bugged_tokens_db']

    test_results = dataset_db.find()
    for token in test_results:
        if float(token['liquidity']['eth_liquidity']) < 0.01:
            is_scam = 1
        else:
            is_scam = 0
        if token['scam'] != is_scam:
            print("updated " + token['address'])

        scam_db['dataset_collection'].update_one({'_id': token['_id']}, {'$set': {'scam': is_scam}}, upsert=False)


def check_scam(dataset):

    dataset_db = scam_db['dataset_collection']
    bugged_tokens_db = scam_db['bugged_tokens_db']

    for index, entry in dataset.iterrows():
        token_address = Web3.toChecksumAddress(entry['address'])

        token_already_scanned = dataset_db.find_one({'address': token_address}, {"_id": 0})
        if token_already_scanned is not None:
            logger.info(f"already scanned {token_address}")
            continue

        logger.info(f"collecting {token_address}")
        liquidity = indicators.liquidity.get_liquidity(token_address)
        number_of_holders = indicators.holders.get_holders(token_address)

        if liquidity['eth_liquidity'] is None:
            fail_object = {
                "address": token_address,
                "liquidity": "no WETH pair",
                "holders": number_of_holders,
            }
            logger.warning(f"Error in {token_address}, no WETH or smth")
            bugged_tokens_db.replace_one({"address": token_address}, fail_object, upsert=True)
            continue

        scam = 0
        if float(liquidity['eth_liquidity']) < 0.01:
            scam = 1

        dataset_object = {
            "address": token_address,
            "liquidity": liquidity,
            "holders": number_of_holders,
            "scam": scam
        }

        dataset_db.replace_one({"address": token_address}, dataset_object, upsert=True)

        logger.info(f"Holders: {len(number_of_holders['holders'])}")
        logger.info(f"WETH: {liquidity['eth_liquidity']}")
        logger.info(f"is scam? {scam}")


if __name__ == '__main__':

    dataset_file = "./dataset/scanned_tokens_csv.csv"
    data = pd.read_csv(dataset_file)

    #change_scam_criteria(data)
    check_scam(data)

