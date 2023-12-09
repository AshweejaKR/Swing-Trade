# -*- coding: utf-8 -*-
"""
Created on Sat Dec  9 22:55:40 2023

@author: ashwe
"""

# importing all required libraries
import logging as lg
import os, sys
import json
import threading
import time
import pandas as pd
import datetime as dt
import pytz

import urllib
from SmartApi import SmartConnect
from pyotp import TOTP

# global variables here
global instrument_list
global client_id
global tickers
global api
global positions

global i
global j

# assigning default values to global variables
filename = ''
instrument_list = None
client_id = None
tickers = None
api = None
positions = {}
full_report = {}

i = 0
j = 5

class MyStreamHandler(lg.Handler):
    terminator = '\n'
    def __init__(self):
        lg.Handler.__init__(self)
        self.stream = sys.stdout
    def emit(self, record):
        if (record.levelno == lg.INFO or record.levelno == lg.WARNING or record.levelno == lg.ERROR):
            try:
                msg = self.format(record)
                stream = self.stream
                stream.write(msg + self.terminator)
                self.flush()
            except RecursionError:
                raise
            except Exception:
                self.handleError(record)

def initialize_logger():
    # creating s folder for the log
    logs_path = './logs/'
    try:
        os.mkdir(logs_path)
    except OSError:
        print('Creation of the directory %s failed - it does not have to be bad' % logs_path)
    else:
        print('Succesfully created log directory')

    # renaming each log depending on time Creation
    date_time = dt.datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y%m%d_%H%M%S")
    log_name = date_time + '.log'
    log_name = 'logger_file.log'
    currentLog_path = logs_path + log_name

    # log parameter
    lg.basicConfig(filename = currentLog_path, format = '%(asctime)s {%(pathname)s:%(lineno)d} [%(threadName)s] - %(levelname)s: %(message)s', level = lg.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')

    # print the log in console
    # console_formatter = lg.Formatter("%(asctime)s {%(pathname)s:%(lineno)d} [%(threadName)s] - %(levelname)s: %(message)s", datefmt='%Y-%m-%d %H:%M:%S')
    console_formatter = lg.Formatter("%(asctime)s : %(message)s", datefmt='%Y-%m-%d %H:%M:%S')
    console_handler = MyStreamHandler()
    console_handler.setFormatter(console_formatter)
    
    # lg.getLogger().addHandler(lg.StreamHandler())
    lg.getLogger().addHandler(console_handler)

    # init message
    lg.info('Log initialized')

# initialize bot for trading account
def initialize_bot():
    global instrument_list
    global tickers

    filename = 'instrument_list.json'
    try:
        with open(filename) as f:
            instrument_list = json.load(f)
    except FileNotFoundError:
        instrument_url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        response = urllib.request.urlopen(instrument_url)
        instrument_list = json.loads(response.read())
        with open(filename, "w") as f:
            f.write(json.dumps(instrument_list))
    except Exception as err:
        template = "An exception of type {0} occurred. error message:{1!r}"
        message = template.format(type(err).__name__, err.args)
        lg.error(message)

    tickers = ["WIPRO","ULTRACEMCO","UPL","TITAN","TECHM","TATASTEEL","TATAMOTORS",
           "TATACONSUM","TCS","SUNPHARMA","SBIN","SBILIFE","RELIANCE","POWERGRID",
           "ONGC","NESTLEIND","NTPC","MARUTI","M&M","LT","KOTAKBANK","JSWSTEEL",
           "INFY","INDUSINDBK","ITC","ICICIBANK","HDFC","HINDUNILVR","HINDALCO",
           "HEROMOTOCO","HDFCLIFE","HDFCBANK","HCLTECH","GRASIM","EICHERMOT",
           "DRREDDY","DIVISLAB","COALINDIA","CIPLA","BRITANNIA","BHARTIARTL",
           "BPCL","BAJAJFINSV","BAJFINANCE","BAJAJ-AUTO","AXISBANK","ASIANPAINT",
           "APOLLOHOSP","ADANIPORTS","ADANIENT"]
    
    lg.info('Trading Bot initialized')
    
def login():
    global client_id
    global api

    try:
        key_secret = open("key.txt","r").read().split()
        client_id = key_secret[2]

        api = SmartConnect(api_key = key_secret[0])
        data = api.generateSession(client_id, key_secret[3], TOTP(key_secret[4]).now())
        lg.debug('data: %s ' % data)
        if(data['status'] and data['message'] == 'SUCCESS'):
            lg.info('Login success ... !')
        else:
            lg.error('Login failed ... !')
    except Exception as err:
        template = "An exception of type {0} occurred. error message:{1!r}"
        message = template.format(type(err).__name__, err.args)
        lg.error(message)
        sys.exit(0)

def logout():
    global client_id
    global api

    try:
        data = api.terminateSession(client_id)
        lg.debug('logout: %s ' % data)
        if(data['status'] and data['message'] == 'SUCCESS'):
            lg.info('Logout success ... !')
        else:
            lg.error('Logout failed ... !')
    except Exception as err:
        template = "An exception of type {0} occurred. error message:{1!r}"
        message = template.format(type(err).__name__, err.args)
        lg.error(message)
        lg.error('Logout failed ... !')

def token_lookup(ticker, exchange = "NSE"):
    global instrument_list

    try:
        for instrument in instrument_list:
            if instrument["name"] == ticker and instrument["exch_seg"] == exchange and instrument["symbol"].split('-')[-1] == "EQ":
                return instrument["token"]
    except Exception as err:
        template = "An exception of type {0} occurred. error message:{1!r}"
        message = template.format(type(err).__name__, err.args)
        lg.error(message)
        
def symbol_lookup(token, exchange = "NSE"):
    global instrument_list

    for instrument in instrument_list:
        if instrument["token"] == token and instrument["exch_seg"] == exchange:
            return instrument["symbol"][:-3]

def get_oder_status(orderID):
    status = 'NA'
    
    time.sleep(2)
    order_history_response = api.orderBook()  
    try:
        for i in order_history_response['data']:
            if(i['orderid'] == orderID):
                status = i['status'] # completed/rejected/open/cancelled
                break
    except Exception as err:
        template = "An exception of type {0} occurred. error message:{1!r}"
        message = template.format(type(err).__name__, err.args)
        lg.error(message)
        
    return status

def hist_data(ticker, duration = 10, interval = 'ONE_DAY', exchange = "NSE"):
    global api
    global instrument_list

    token = token_lookup(ticker)
    if token is None:
        lg.error("Not a VALID ticker")
        df_data = pd.DataFrame(columns = ["date", "open", "high", "low", "close", "volume"])
        return df_data
    params = {
             "exchange" : exchange,
             "symboltoken" : token,
             "interval" : interval,
             "fromdate" : (dt.date.today() - dt.timedelta(duration)).strftime('%Y-%m-%d %H:%M'),
             "todate" : dt.date.today().strftime('%Y-%m-%d %H:%M')  
             }

    data = api.getCandleData(params)

    df_data = pd.DataFrame(data["data"],
                           columns = ["date", "open", "high", "low", "close", "volume"])
    df_data.set_index("date", inplace = True)
    df_data.index = pd.to_datetime(df_data.index)
    df_data.index = df_data.index.tz_localize(None)
    return df_data

def add_position(name, symbol, qty, buy_date, buy_price, asset_type = 'EQ'):
    global positions
    global full_report
    positions[name] = {}
    positions[name]['name'] = name
    positions[name]['symbol'] = symbol
    positions[name]['qty'] = qty
    positions[name]['buy_date'] = buy_date.strftime('%m/%d/%Y')
    positions[name]['sell_date'] = None
    positions[name]['sell_price'] = 0.0
    positions[name]['buy_price'] = buy_price
    positions[name]['asset_type'] = asset_type
    positions[name]['isClosed'] = False

    full_report[name] = {}
    full_report[name]['name'] = name
    full_report[name]['symbol'] = symbol
    full_report[name]['qty'] = qty
    full_report[name]['buy_date'] = buy_date.strftime('%m-%d-%Y')
    full_report[name]['sell_date'] = None
    full_report[name]['sell_price'] = 0.0
    full_report[name]['buy_price'] = buy_price
    full_report[name]['asset_type'] = asset_type
    full_report[name]['isClosed'] = False
    
def remove_position(name, sell_date, sell_price):
    global positions
    global full_report

    if name in full_report:
        full_report[name]['sell_date'] = sell_date.strftime('%m-%d-%Y')
        full_report[name]['sell_price'] = sell_price
        full_report[name]['isClosed'] = True

    if name in positions:
        del positions[name]
        print("{symbol} was successfully removed.".format(symbol=name))
    else:
        print("{symbol} did not exist in the porfolio.".format(symbol=name))

def save_position(filename = 'positions.json'):
    global positions
    global full_report
    lg.debug('positions list: %s ' % positions)
    lg.debug('full_report list: %s ' % full_report)
    try:
        with open(filename, "w") as f:
            f.write(json.dumps(positions))

        with open('full_report.json', "w") as f:
            f.write(json.dumps(full_report))
    except Exception as err:
        template = "An exception of type {0} occurred. error message:{1!r}"
        message = template.format(type(err).__name__, err.args)
        lg.error(message)

def get_position(filename = 'positions.json'):
    global positions
    global full_report

    try:
        with open(filename) as f:
            positions = json.load(f)

        with open('full_report.json') as f:
            full_report = json.load(f)
    except FileNotFoundError:
        positions = {}
        full_report = {}
    except Exception as err:
        template = "An exception of type {0} occurred. error message:{1!r}"
        message = template.format(type(err).__name__, err.args)
        lg.error(message)

def check_position():
    global positions
    global api

    rem_list = []
    try:
        holdings = api.holding()
        lg.debug('holdings: %s ' % holdings)

        if(holdings['status'] and (holdings['message'] == 'SUCCESS')):
            holdings_data = holdings['data']
            for i in positions:
                for j in holdings_data:
                    if positions[i]['symbol'] in j['tradingsymbol']:
                        lg.info('positions exist for : %s ' % positions[i]['symbol'])
                    else:
                        lg.error('positions does NOT exist for : %s ' % positions[i]['symbol'])
                        rem_list.append(i)

        for i in rem_list:
            del positions[i]
        save_position()
    except Exception as err:
        template = "An exception of type {0} occurred. error message:{1!r}"
        message = template.format(type(err).__name__, err.args)
        lg.error(message)

class Trader(threading.Thread):
    def __init__(self, api, name, ticker, entryPrice, trend='NA'):
        # Initialize with ticker and api
        self.api = api
        self.thread_name = name
        self.ticker = ticker
        self.trend = trend
        self.entryPrice = entryPrice
        self.takeProfit = (entryPrice * 1.02)

        try:
            self.thread_name = self.ticker + '_at_' + str(self.entryPrice)
            threading.Thread.__init__(self, name=self.thread_name)
            lg.info('Trade initialized with ticker %s ...!!' % (self.ticker))
            if(trend == 'NA'):
                orderID = self.submit_order(10)
                count = 0
                while (get_oder_status(orderID) == 'open'):
                    lg.info('%s: Buy order in open, waiting ... %d ' % (self.thread_name, count))
                    count = count + 1
                status = get_oder_status(orderID)
                if(status == 'completed'):
                    lg.info('Buy order submitted correctly...! Qty = %d, Order Price = %f' % (10, entryPrice))
                    buy_date = dt.datetime.now(pytz.timezone("Asia/Kolkata")).time()
                    add_position(self.thread_name, self.ticker, 10, buy_date, entryPrice)
                    save_position()
                    self.start()
                else:
                    lg.error('Buy order NOT submitted, aborting trade!')
                    sys.exit()
        except Exception as err:
            template = "An exception of type {0} occurred. error message:{1!r}"
            message = template.format(type(err).__name__, err.args)
            lg.error(message)
            lg.error('Buy order NOT submitted, aborting trade!')
            sys.exit()

    def set_takeprofit(self, entryPrice):
        try:
            self.takeProfit = entryPrice * 1.015
            lg.info('Set target for trigger price: %f at %f' % (self.trigger, self.takeProfit))
        except Exception as err:
            template = "An exception of type {0} occurred. error message:{1!r}"
            message = template.format(type(err).__name__, err.args)
            lg.error(message)

    def trail_SL(self):
        pass

    def get_current_price(self):
        return 0.0
    
    def submit_order(self, sharesQty, exit = False, exchange = 'NSE'):
        global ltp
        buy_sell = None
        if(exit):
            buy_sell = 'SELL'
        else:
            buy_sell = 'BUY'
        lg.info('Submitting %s Order for %s, Qty = %d ' % (buy_sell, self.ticker, sharesQty))
        
        try:
            price = get_ltp(self.ticker)
            params = {
                    "variety" : "NORMAL",
                    "tradingsymbol" : "{}-EQ".format(self.ticker),
                    "symboltoken" : token_lookup(self.ticker),
                    "transactiontype" : buy_sell,
                    "exchange" : exchange,
                    "ordertype" : "MARKET",
                    "producttype" : "DELIVERY",
                    "duration" : "DAY",
                    "price" : price,
                    "quantity" : sharesQty
                    }
            
            lg.debug('params: %s ' % params)

            orderID = self.api.placeOrder(params)
        except Exception as err:
            template = "An exception of type {0} occurred. error message:{1!r}"
            message = template.format(type(err).__name__, err.args)
            lg.error(message)
            lg.error('%s order NOT submitted!' % buy_sell)
            sys.exit()
        return orderID
    
    def run(self):
        startTime = dt.time(9, 15)
        endTime = dt.time(16, 50)

        while True:
            time.sleep(1)
            lg.info('EXIT: Running trade for %s ... !' % (self.ticker))
            
            cur_time = dt.datetime.now(pytz.timezone("Asia/Kolkata")).time()
            if(cur_time < startTime or cur_time > endTime):
                lg.info('Market is closed. ')
                sys.exit()
            
            cur_price = get_ltp(self.ticker, 'sell')
            lg.debug('SELL: Current price for %s is %f ' % (self.ticker, cur_price))
            lg.debug('SELL: take profit for %s is %f ' % (self.ticker, self.takeProfit))

            if(self.takeProfit < cur_price):
                orderID = self.submit_order(10, True)
                count = 0
                while (get_oder_status(orderID) == 'open'):
                    lg.info('%s: Sell order in open, waiting ... %d ' % (self.thread_name, count))
                    count = count + 1
                status = get_oder_status(orderID)
                if(status == 'completed'):
                    lg.info('Sell order submitted correctly...! Qty = %d, Order Price = %f' % (10, cur_price))
                    remove_position(self.thread_name, cur_time, cur_price)
                    save_position()
                    sys.exit()
                else:
                    lg.error('Sell order NOT submitted, aborting trade!')
                    sys.exit()
                
def get_ltp(tradingsymbol, test='NA'):
    global ltp
    global i
    global j

    try:
        data = api.ltpData(exchange='NSE', tradingsymbol=tradingsymbol, symboltoken=token_lookup(tradingsymbol))
        if(data['status'] and (data['message'] == 'SUCCESS')):
            ltp = float(data['data']['ltp'])
        else:
            template = "An ERROR occurred. error message : {0!r}"
            message = template.format(data['message'])
            lg.error(message)
            sys.exit()
    except Exception as err:
        template = "An exception of type {0} occurred. error message:{1!r}"
        message = template.format(type(err).__name__, err.args)
        lg.error(message)
    return ltp

def swing_strategy(tradingsymbol, temp):
    prev_close = temp
    startTime = dt.time(9, 15)
    endTime = dt.time(15, 15)
    
    lg.info('Trade is started ... !')
    while True:
        time.sleep(1)
        lg.info('ENTER: Running trade for %s ... !' % (tradingsymbol))

        cur_time = dt.datetime.now(pytz.timezone("Asia/Kolkata")).time()
        if(cur_time < startTime or cur_time > endTime):
            lg.info('Market is closed. ')
            sys.exit()

        cur_price = get_ltp(tradingsymbol, 'buy')
        lg.debug('BUY: Current price for %s is %f ' % (tradingsymbol, cur_price))
        lg.debug('BUY: prev close for %s is %f ' % (tradingsymbol, prev_close))
        lg.debug('BUY: trigger price for %s is %f ' % (tradingsymbol, (0.9 * prev_close)))

        if(cur_price < (0.99 * prev_close)):
            obj = Trader(api, '', tradingsymbol, cur_price)
            prev_close = cur_price    
    
    
def main():
    global api
    global instrument_list
    global positions
    global full_report
    global ltp
    positions_list = []

    # initialize the logger (imported from logger)
    initialize_logger()

    # initialize bot
    initialize_bot()

    login()

    get_position()  
      
    # check position
    check_position()

    # Trade Exit
    for i in positions:
        obj = Trader(api, '', positions[i]['symbol'], positions[i]['buy_price'], 'long')
        positions_list.append(obj)

    for i in positions_list:
        i.start()

    # Trade Enter
    tradingsymbol = 'INFY'
    stock_data = hist_data(tradingsymbol)
    prev_close = stock_data.iloc[-1]['close']

    swing_strategy(tradingsymbol, prev_close)

    for i in positions_list:
        i.join()

    logout()

    lg.info('Trading was successful!')
    lg.info('Trading Bot finished ... ')
    lg.info ("Exiting Main Thread")

if __name__ == '__main__':
    main()