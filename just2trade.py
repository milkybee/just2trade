#!/usr/bin/python
"""
A simple Python wrapper around the trading API published
at http://www.just2trade.com/trading_tools/api.

Note, you must have a trading account in order to access the API.
"""

VERSION = (0, 9, 2)
__version__ = '.'.join(map(str, VERSION))

import logging
import os
import select
import socket
import sys
import urllib2
import time
import datetime
from threading import Thread, Lock
from xml.etree import cElementTree as ElementTree
from collections import defaultdict
from decimal import Decimal

CREDENTIALS_FILE = os.path.expanduser(
    os.environ.get('JUST2TRADE_CREDENTIALS_FILE', '~/.just2trade'))
ENVIRON_USERNAME = 'JUST2TRADE_USERNAME'
ENVIRON_PASSWORD = 'JUST2TRADE_PASSWORD'

MODE_TEST = 'TSTA' # test
MODE_JUST2TRADE = 'STJT' # production
MODE_LOWTRADES = 'STSS'
MODES = (
    MODE_TEST,
    MODE_JUST2TRADE,
    MODE_LOWTRADES,
)

SOH = chr(0x01)
EOT = chr(0x04)

TAGS = dict(
    
    USER_ACCOUNT_NUMBER = '1',
    
    # Always in the form AAAANNNN.
    ORDER_ID = '11',
    
    COMMISSION = '12',
    
    QUANTITY_EXECUTED = '14',
    
    PRICE_OF_LAST_FILL = '31',
    
    QUANTITY_FILLED = '32',
    
    MESSAGE_TYPE = '35',
    
    # Must be greater than 0.
    ORDER_QUANTITY = '38',
    
    ORDER_STATUS = '39',
              
    ORDER_TYPE = '40',
    
    REFERENCE_ORDER_ID = '41',
    
    LIMIT_PRICE = '44',
    
    USERNAME = '50',
    
    HEARTBEAT_TIMESTAMP = '52',#UNDOCUMENTED AS OF 2013-2-11
    
    SIDE_OF_ORDER = '54',
    
    SYMBOL = '55',
    
    TEXT = '58',
    
    TIME_IN_FORCE = '59',
    
    # yyyy-mm-dd hh:mm:ss (time is Eastern time)
    TRANSACTION_TIME = '60',
    
    BROKER_ID = '76',
        
    USER_DATA = '96',
    
    STOP_PRICE = '99',
    
    # Valid value is any one of the destinations returned at login
    # in tag 13000.
    DESTINATION_FOR_ORDER = '100',
    
    SECURITY_TYPE = '167',
    
    USER_STATUS = '926',
    
    # Returned by the authentication server at successful login.
    SERVER_ID_KEY = '11999',
    
    TRADING_SERVER_IP_ADDRESS = '12000',
    
    TRADING_SERVER_PORT = '12001',
    
    UNUSED1 = '12002',
    
    UNUSED2 = '12003',
    
    # Semi-colon delimited list of destinations available to the client.
    ORDER_ROUTES = '13000',
    
    ACCOUNT_TYPE = '13001',
    
    CASH_TRADE_BALANCE = '13002',
    
    MARGIN_TRADE_BALANCE = '13003',
    
    INTERNAL_USE = '13005',
    
    # current daytrading buying power available
    INTERNAL_USE2 = '13008',
    
    # buying power multiplier
    # 1 (cash account)
    # 2 (margin account)
    # 4 (if you have been designated as a daytrader)
    INTERNAL_USE3 = '13009',
)
TAG_VALUE_TO_NAME = {}
for _k, _v in TAGS.iteritems():
    exec '%s = %s' % (_k, repr(_v))
    TAG_VALUE_TO_NAME[_v] = _k
TAG_VALUES = TAGS.values() # {tag: tag_name}

ACCOUNT_TYPE_VALUES = dict(
    ACCOUNT_TYPE_CASH = 1,
    ACCOUNT_TYPE_MARGIN = 2,
    ACCOUNT_TYPE_SHORT = 3,
)
for _k, _v in ACCOUNT_TYPE_VALUES.iteritems():
    exec '%s = %s' % (_k, repr(_v))

MESSAGE_TYPE_VALUES = dict(
    # To server:
    MESSAGE_TYPE_LOGON_REQUEST = 'A',
    MESSAGE_TYPE_NEW_ORDER_REQUEST = 'D',
    MESSAGE_TYPE_CANCEL_ORDER_REQUEST = 'F',
    MESSAGE_TYPE_HEARTBEAT = 0,
    MESSAGE_TYPE_SHORTLIST_REQUEST = 'x',
    MESSAGE_TYPE_POSITION_UPDATE_REQUEST = 'AN',
    MESSAGE_TYPE_BALANCE_UPDATE_REQUEST = 'AX',
    MESSAGE_TYPE_TRADE_UPDATE_REQUEST = 'AQ',
    
    # From server:
    MESSAGE_TYPE_LOGON_RESPONSE = 'A',
    MESSAGE_TYPE_ORDER_REJECTION = 3,
    MESSAGE_TYPE_EXECUTION_REPORT = 8,
    MESSAGE_TYPE_CANCEL_ORDER_REJECTION = 9,
    MESSAGE_TYPE_TRADING_DESTINATION_REPORT = 'dr',
    MESSAGE_TYPE_POSITION_REPORT = 'yr',
    MESSAGE_TYPE_ACCOUNT_REPORT = 'br',
    MESSAGE_TYPE_SHORTLIST_ENTRY = 'x',
)
for _k, _v in MESSAGE_TYPE_VALUES.iteritems():
    exec '%s = %s' % (_k, repr(_v))

ORDER_STATUS_VALUES = dict(
    ORDER_STATUS_NEW = 'A',
    ORDER_STATUS_OPEN = 0,
    ORDER_STATUS_PARTIALLY_FILLED = 1,
    ORDER_STATUS_FILLED = 2,
    ORDER_STATUS_CANCELLED = 4,
    ORDER_STATUS_PENDING_CANCEL = 6,
    ORDER_STATUS_REJECTED = 8,
)
for _k, _v in ORDER_STATUS_VALUES.iteritems():
    exec '%s = %s' % (_k, repr(_v))

ORDER_TYPE_VALUES = dict(
    ORDER_TYPE_MARKET = 1,
    ORDER_TYPE_LIMIT = 2,
    ORDER_TYPE_STOP = 3,
    ORDER_TYPE_STOP_LIMIT = 4,
    ORDER_TYPE_MARKET_ON_CLOSE = 6,
)
for _k, _v in ORDER_TYPE_VALUES.iteritems():
    exec '%s = %s' % (_k, repr(_v))

SECURITY_TYPE_VALUES = dict(
    SECURITY_TYPE_EQUITY = 1,
    SECURITY_TYPE_EQUITY_OPTION = 2,
)
for _k, _v in SECURITY_TYPE_VALUES.iteritems():
    exec '%s = %s' % (_k, repr(_v))

BROKER_ID_VALUES = dict(
    BROKER_ID_LOWTRADES = 'STSS',
    BROKER_ID_JUST2TRADE = 'STJT',
    BROKER_ID_TEST = 'TEST',
    BROKER_ID_TSTA = 'TSTA', # redundant?
)
for _k, _v in BROKER_ID_VALUES.iteritems():
    exec '%s = %s' % (_k, repr(_v))

USER_STATUS_VALUES = dict(
    USER_STATUS_LOGGED_IN = 1,
    USER_STATUS_NOT_LOGGED_IN = 2,
    USER_STATUS_NO_SUCH_USER = 3,
    USER_STATUS_INCORRECT_PASSWORD = 4,
)
for _k, _v in USER_STATUS_VALUES.iteritems():
    exec '%s = %s' % (_k, repr(_v))

SIDE_OF_ORDER_VALUES = dict(
    SIDE_OF_ORDER_BUY = 1,
    SIDE_OF_ORDER_SELL = 2,
    SIDE_OF_ORDER_SELL_SHORT = 5,
    SIDE_OF_ORDER_BUY_TO_COVER = 'BC',
)
for _k, _v in SIDE_OF_ORDER_VALUES.iteritems():
    exec '%s = %s' % (_k, repr(_v))

TIME_IN_FORCE_VALUES = dict(
    TIME_IN_FORCE_GOOD_FOR_DAY = 0,
    TIME_IN_FORCE_GOOD_TIL_CANCEL = 1,
    TIME_IN_FORCE_DAY_PLUS_EXTENDED_HOURS = 5,
)
for _k, _v in TIME_IN_FORCE_VALUES.iteritems():
    exec '%s = %s' % (_k, repr(_v))

DECIMAL_FIELDS = (
    CASH_TRADE_BALANCE,
    COMMISSION,
    LIMIT_PRICE,
    MARGIN_TRADE_BALANCE,
    PRICE_OF_LAST_FILL,
    STOP_PRICE,
)

#logging.basicConfig()
#LOG = logging.getLogger(__file__)
#LOG.setLevel(logging.INFO)
#
#class InfoFilter(logging.Filter):
#    def filter(self, rec):
#        return rec.levelno in (logging.DEBUG, logging.INFO)

# Ensure .info() goes to stdout, not the default stderr.
#TODO:fix? neither solutions work? Calls to LOG.info() still go to stderr?!
#solution1
#h1 = logging.StreamHandler(sys.__stdout__)
#h1.setLevel(logging.INFO)
#h1.addFilter(InfoFilter())
#LOG.addHandler(h1)
#solution2
#ch = logging.StreamHandler(sys.__stdout__)
#ch.setLevel(logging.INFO)
#LOG.addHandler(ch)

class Logger(object):
    
    def info(self, *args):
        s = ' '.join(map(str, args))
        print s
    
    def error(self, *args):
        s = ' '.join(map(str, args))
        print>>sys.__stderr__, s
        
LOG = Logger()

class XmlListConfig(list):
    def __init__(self, aList):
        for element in aList:
            if element:
                # treat like dict
                if len(element) == 1 or element[0].tag != element[1].tag:
                    self.append(XmlDictConfig(element))
                # treat like list
                elif element[0].tag == element[1].tag:
                    self.append(XmlListConfig(element))
            elif element.text:
                text = element.text.strip()
                if text:
                    self.append(text)

class XmlDictConfig(dict):
    '''
    Example usage:

    >>> tree = ElementTree.parse('your_file.xml')
    >>> root = tree.getroot()
    >>> xmldict = XmlDictConfig(root)

    Or, if you want to use an XML string:

    >>> root = ElementTree.XML(xml_string)
    >>> xmldict = XmlDictConfig(root)

    And then use xmldict for what it is... a dict.
    '''
    def __init__(self, parent_element):
        if parent_element.items():
            self.update(dict(parent_element.items()))
        for element in parent_element:
            if element:
                # treat like dict - we assume that if the first two tags
                # in a series are different, then they are all different.
                if len(element) == 1 or element[0].tag != element[1].tag:
                    aDict = XmlDictConfig(element)
                # treat like list - we assume that if the first two tags
                # in a series are the same, then the rest are the same.
                else:
                    # here, we put the list in dictionary; the key is the
                    # tag name the list elements all share in common, and
                    # the value is the list itself 
                    aDict = {element[0].tag: XmlListConfig(element)}
                # if the tag has attributes, add those to the dict
                if element.items():
                    aDict.update(dict(element.items()))
                self.update({element.tag: aDict})
            # this assumes that if you've got an attribute in a tag,
            # you won't be having any text. This may or may not be a 
            # good idea -- time will tell. It works for the way we are
            # currently doing XML configuration files...
            elif element.items():
                self.update({element.tag: dict(element.items())})
            # finally, if there are no child tags and no attributes, extract
            # the text
            else:
                self.update({element.tag: element.text})

class AuthenticationError(Exception):
    pass

class Message(dict):
    """
    Represents a single complete communication to or from the server.
    """
    
    @classmethod
    def from_string(cls, s):
        parts = s.strip().split(SOH)
        msg = cls()
        for part in parts:
            if not part.strip():
                continue
            k, v  = part.split('=')
            
            if v.isdigit():
                v = int(v)
            elif k == TRANSACTION_TIME:
                v = datetime.datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
            elif k in DECIMAL_FIELDS:
                v = Decimal(v)
                
            assert k in TAG_VALUES, \
                'Invalid tag: [%s] (type=%s)\nMust be one of:\n%s' \
                    % (k, type(k).__name__, '\n'.join(sorted(TAG_VALUES)))
            msg[k] = v
        return msg
    
    def to_string(self):
        s = (SOH.join('%s=%s' % (k, v) for k, v in self.iteritems()))
        return SOH + s + EOT
    
    def __repr__(self):
        s = []
        s.append('Message({')
        for k, v in self.iteritems():
            pk = TAG_VALUE_TO_NAME.get(k, k)
            try:
                values_dict = eval(pk+'_VALUES')
                pv = dict((_2, _1) for _1, _2 in values_dict.iteritems())[v]
            except NameError, e:
                pv = repr(v)
            s.append('    %s: %s,' % (pk, pv))
        s.append('})')
        return '\n'.join(s)
        
    def pprint(self):
        print repr(self)

class Order(object):
    """
    Manages a single trade on an equity.
    """
    
    def __init__(self, api, symbol):
        self.api = api
        self.symbol = symbol
        self.request = None
        self._response = None
        self._responses = []
        self._order_id = None
        self._status = None
    
    @property
    def response(self):
        return self._response
    
    @response.setter
    def response(self, r):
        self._response = r
        if r:
            self._order_id = r[ORDER_ID]
            self._status = r[ORDER_STATUS]
            self._responses.append(r)
    
    @property
    def order_id(self):
        return self._order_id
    
    @property
    def status(self):
        return self._status
    
    @property
    def is_terminal(self):
        status = self._status
        if status is None:
            return False
        return status in (
            ORDER_STATUS_FILLED,
            ORDER_STATUS_CANCELLED,
            ORDER_STATUS_REJECTED,
        )
        
    @property
    def is_cancelled(self):
        return self.status == ORDER_STATUS_CANCELLED
    
    @property
    def is_filled(self):
        return self.status == ORDER_STATUS_FILLED
    
    def cancel(self, block=True, block_until_sent=True):
        """
        Note: tag 41 contains the unique order identifier assigned by the API
        server. This instruction will be a request to cancel all remaining
        unfilled shares of the order. There is no support for partial cancels.
        You should not attempt (and it is not necessary) to send cancellation
        requests for day or day+extended hours orders after the market session
        has closed. The system will automatically expire these orders.
        """
        assert not self.is_terminal, \
            'Order has terminated: %s' % (self.status,)
        LOG.info('Cancelling %s...' % self.order_id)
        message = Message({
            MESSAGE_TYPE: MESSAGE_TYPE_CANCEL_ORDER_REQUEST,
            REFERENCE_ORDER_ID: self.order_id,
            SERVER_ID_KEY: self.api.serverkey,
            USER_ACCOUNT_NUMBER: self.api.account_number,
            BROKER_ID: self.api.mode,
        })
        self.response = None
        self.api.push_outgoing(message)
        if block_until_sent:
            # Wait until our message is sent.
            # We don't necessarily care yet if we receive a response.
            while 1:
                if not self.api.pending_outgoing(message):
                    break
                LOG.info('Waiting for message to be sent...')
                time.sleep(1)
        if block:
            # Wait until order cancelled or explicit cancellation failure.
            while 1:
                if self.order_id is not None:
                    break
                LOG.info('Waiting for order to receive ID...')
                time.sleep(1)
            while 1:
                LOG.info('Waiting for order %s to be cancelled...' % self.order_id)
                if self.is_terminal:#status == ORDER_STATUS_CANCELLED:
                    break
                message = self.api.wait_for_message(**{ORDER_ID: self.order_id})
                if message[MESSAGE_TYPE] == MESSAGE_TYPE_CANCEL_ORDER_REJECTION:
                    raise Exception, 'Unable to cancel order: %s' % (message,)
                elif message.get(ORDER_STATUS) == ORDER_STATUS_PENDING_CANCEL:
                    # Continue waiting.
                    LOG.info(('Order %s is pending cancellation. ' + \
                        'Continuing to wait...') % self.order_id)
                    pass
                elif message.get(ORDER_STATUS) == ORDER_STATUS_CANCELLED:
                    LOG.info('Order %s was cancelled.' % self.order_id)
                    break
        return self
        
    def wait_for_completion(self):
        """
        Blocks until the order reaches a terminal status.
        """
        while 1:
            LOG.info('Waiting for order %s to complete...' % self.order_id)
            if self.is_terminal:
                break
            message = self.api.wait_for_message(**{ORDER_ID: self.order_id})
            if message[MESSAGE_TYPE] == ORDER_STATUS_FILLED:
                break
        return self
        
    def wait_for_response(self):
        """
        Blocks until any response is received for this explicit order.
        """
        while 1:
            if self.response:
                return
            time.sleep(1)

class J2T(object):
    """
    Allows accessing the Just2Trade API via a Python instance.
    """
    
    def __init__(self, mode=MODE_JUST2TRADE, login=None):
        assert mode in MODES, 'Invalid mode: %s' % (mode,)
        self.mode = mode
        self._current_account_number = None
        if login:
            self.username, self.password = login
        elif os.path.isfile(CREDENTIALS_FILE):
            # Get login from credentials file.
            self.username, self.password = open(CREDENTIALS_FILE, 'r')\
                .read().strip().split('\n')
        else:
            # Get login from environment variables.
            self.username = os.environ.get(ENVIRON_USERNAME)
            self.password = os.environ.get(ENVIRON_PASSWORD)
        assert self.username, 'Invalid username.'
        assert self.password, 'Invalid password.'
        self._auth = None
        self._logged_on = False
        self._connection = None
        
        self._out_queue = []
        self._out_queue_lock = Lock()
        
        self._in_queue = []
        self._in_queue_lock = Lock()
        
        self._last_message_time = None
        
        self._accounts = {}
        
        # Orders we've sent to the server but are waiting to get
        # a confirmation message.
        self._pending_orders = {} # {symbol:order}
        
        self._orders = {} # {order_id:order}
        
        self._positions = {} # {account_number: {symbol: message}}
    
    @property
    def orders(self):
        return self._orders
    
    @property
    def serverkey(self):
        return self._auth['SessionKey']

    @property
    def account_number(self):
        return self._current_account_number

    @account_number.setter
    def account_number(self, n):
        assert n in self._accounts, 'Unknown account number: %s' % (n,)
        self._current_account_number = n

    @property
    def account(self):
        return self._accounts[self.account_number]

    @property
    def account_type(self):
        return self._accounts[self.account_number][ACCOUNT_TYPE]
    
    @property
    def destination(self):
        return self._current_destination
    
    @property
    def positions(self):
        """
        Returns positions for the currently selected account number,
        in the form {symbol:data}.
        """
        return self._positions.get(self.account_number, {})
    
    def on_A(self, message):
        """
        Handle logon response.
        """
        status = message[USER_STATUS]
        if status != USER_STATUS_LOGGED_IN:
            errors = dict((v, k) for k, v in USER_STATUS_VALUES.iteritems())
            error_message = errors[status]
            raise Exception, error_message
        self._logged_on = True
    
    def on_yr(self, message):
        """
        Handle MESSAGE_TYPE_POSITION_REPORT.
        """
        account_number = message[USER_ACCOUNT_NUMBER]
        symbol = message[SYMBOL]
        self._positions.setdefault(account_number, {})
        self._positions[account_number][symbol] = message
    
    def on_br(self, message):
        """
        Handle balance and position report for an account.
        """
        self._current_account_number = message[USER_ACCOUNT_NUMBER]
        self._accounts[message[USER_ACCOUNT_NUMBER]] = message
        
    def on_dr(self, message):
        """
        Handle route destinations.
        """
        self._destinations = [
            _.strip() for _ in message[ORDER_ROUTES].split(';') if _.strip()
        ]
        if self._destinations:
            self._current_destination = self._destinations[0]
    
    def on_8(self, message):
        """
        Handle MESSAGE_TYPE_EXECUTION_REPORT.
        """
        symbol = message[SYMBOL]
        order_id = message[ORDER_ID]
        if symbol in self._pending_orders:
            LOG.info('Removing order from pending set for %s...' % symbol)
            order = self._pending_orders[symbol]
            del self._pending_orders[symbol]
        elif order_id in self._orders:
            LOG.info('Looking up old order for %s...' % symbol)
            order = self._orders[order_id]
        else:
            LOG.info('Creating new order for %s...' % symbol)
            order = Order(api=self, symbol=symbol)
        self._orders[order_id] = order
        order.response = message
    
    def on_9(self, message):
        """
        Handle MESSAGE_TYPE_CANCEL_ORDER_REJECTION.
        """
        order_id = message[ORDER_ID]
        order = self._orders[message[ORDER_ID]]
        order.response = message
    
    def push_outgoing(self, message):
        """
        Queues a message to be sent.
        """
        assert isinstance(message, Message)
        self._out_queue_lock.acquire()
        try:
            self._out_queue.append(message)
        finally:
            self._out_queue_lock.release()
    
    def pending_outgoing(self, message):
        """
        Returns true if message has not yet been sent.
        Returns false otherwise.
        """
        assert isinstance(message, Message)
        self._out_queue_lock.acquire()
        try:
            return message in self._out_queue
        finally:
            self._out_queue_lock.release()
            
    def pop_outgoing(self):
        """
        Retrieves the oldest message received.
        """
        self._out_queue_lock.acquire()
        try:
            if self._out_queue:
                return self._out_queue.pop(0)
        finally:
            self._out_queue_lock.release()
    
    def push_incoming(self, message):
        """
        Adds a received message to the incoming queue.
        """
        assert isinstance(message, Message)
        self._in_queue_lock.acquire()
        try:
            self._in_queue.append(message)
        finally:
            self._in_queue_lock.release()
    
    def pop_incoming(self):
        """
        Retrieves the oldest message received.
        """
        self._in_queue_lock.acquire()
        try:
            if self._in_queue:
                return self._in_queue.pop(0)
        finally:
            self._in_queue_lock.release()

    @property
    def is_authenticated(self):
        return bool(self._auth)

    def authenticate(self):
        """
        Retrieves an authentication token for connecting to the server.
        """
        LOG.info('Authenticating...')
        self._auth = None
        args = dict(user=self.username, password=self.password)
        url = ({
            MODE_TEST: 'http://apitest.bptrade.net/cgi-bin/' + \
                'serviceAPIAuthenticator.cgi?user=%(user)s&device=API' + \
                '&password=%(password)s',
            MODE_JUST2TRADE: 'https://trading.just2trade.com/cgi-bin/' + \
                'serviceAPIAuthenticator.cgi?user=%(user)s&device=API' + \
                '&password=%(password)s',
            MODE_LOWTRADES: 'https://trading.lowtrades.net/cgi-bin/' + \
                'serviceAPIAuthenticator.cgi?user=%(user)s&device=API' + \
                '&password=%(password)s',
        }[self.mode]) % args
        LOG.info('Retrieving authentication URL...')
        xml_response = urllib2.urlopen(url).read()
        LOG.info('Processing response...')
        root = ElementTree.XML(xml_response)
        xmldict = XmlDictConfig(root)
        LOG.info('Response: %s' % repr(xmldict))
        if xmldict['Status'] != '1':
            LOG.error('Authentication failure.')
            xmldict['Message'] = 'Your login attempt has failed. Email ' + \
                'apisupport@just2trade.com for assistance or if you ' + \
                'require further explanation.'
            raise AuthenticationError(xmldict)
        else:
            LOG.info('Authentication success!')
            # A successful response should look like:
            #<api-authentication>
            #<user>username</user>
            #<device>API</device>
            #<TradeServerIP>75.102.12.197</TradeServerIP>
            #<TradeServerPort>23000</TradeServerPort>
            #<SessionKey>ABXP25794</SessionKey>
            #<Status>1</Status>
            #</api-authentication>
            self._auth = xmldict

    @property
    def is_connected(self):
        return bool(self._connection)

    def _handle_connection(self, timeout=1):
        """
        Manages I/O on the socket.
        """
        self._running = True
        self._last_message_time = None
        while self._running:
            inputready, outputready, exceptready = select.select(
                [self._connection],
                [self._connection],
                [],
                timeout
            )
            
            if inputready:
                message = self.get_message()
                self._last_message_time = time.time()
                LOG.info('Received: %s' % message)
                mt = message[MESSAGE_TYPE]
                callback_func_name = 'on_%s' % mt
                if hasattr(self, callback_func_name):
                    getattr(self, callback_func_name)(message)
                self.push_incoming(message)
            
            if outputready:
                message = self.pop_outgoing()
                if message:
                    LOG.info('Sending: %s' % message)
                    self._connection.sendall(message.to_string())
                else:
                    #LOG.info('Sleeping because nothing to send...')
                    time.sleep(timeout)
        LOG.info('Connection handler terminated.')

    def connect(self,
        timeout=1,
        wait_for_report=True,
        message_wait_seconds = 10):
        """
        Establishes a connection to the API server.
        """
        if not self.is_authenticated:
            self.authenticate()
        self.disconnect()
        assert self._auth, 'Not authenticated.'
        
        LOG.info('Creating socket...')
        self._connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._connection.settimeout(timeout)
        #self._connection.setblocking(0)
        
        ip = self._auth['TradeServerIP']
        port = int(self._auth['TradeServerPort'])
        LOG.info('Connecting to %s:%i...' % (ip, port))
        self._connection.connect((ip, port))

        # Queue login message.
        self.push_outgoing(Message({
            MESSAGE_TYPE: MESSAGE_TYPE_LOGON_REQUEST,
            SERVER_ID_KEY: self.serverkey,
            USERNAME: self.username,
            BROKER_ID: self.mode,
        }))
        
        self._processing_thread = Thread(
            target=self._handle_connection,
            kwargs=dict(timeout=timeout))
        self._processing_thread.daemon = True
        self._processing_thread.start()
        
        # Wait until we get a logon response, destination report,
        # and account status.
        if wait_for_report:
            LOG.info('Waiting for account report...')
            self.wait_for_message(**{MESSAGE_TYPE: MESSAGE_TYPE_ACCOUNT_REPORT})
            
            while 1:
                LOG.info('Waiting to receive all messages...')
                if self._last_message_time is None:
                    pass
                else:
                    td = (time.time() - self._last_message_time)
                    if td >= message_wait_seconds:
                        LOG.info('No messages received for %i seconds.' % message_wait_seconds)
                        break
                time.sleep(1)
        
    def disconnect(self):
        if self._connection:
            LOG.info('Cleaning up old connection...')
            self._connection.close()
            self._connection = None
            self._logged_on = False
            self._running = False
            if self._processing_thread:
                self._processing_thread.join()
                self._processing_thread = None
            
    def get_message(self):
        """
        Receives a single complete message.
        """
        assert self.is_connected, 'Not connected.'
        buffer = []
        while 1:
            data = self._connection.recv(1)
            if data == EOT:
                return Message.from_string(''.join(buffer))
            buffer.append(data)

    def wait_for_message(self, **kwargs):
        """
        Returns the first message received of the given type
        and removes it from the incoming queue.
        """
        while 1:
            self._in_queue_lock.acquire()
            try:
                i = 0
                for message in self._in_queue:
                    valid = True
                    if kwargs:
                        for k, v in kwargs.iteritems():
                            if message.get(k) != v:
                                valid = False
                                break
                    if valid:
                        self._in_queue.pop(i)
                        return message
                    i += 1
            finally:
                self._in_queue_lock.release()
            time.sleep(1)

    def order(self, side, symbol, qty, **kwargs):
        
        last_order = self._pending_orders.get(symbol)
        assert not last_order or last_order.is_executed, \
            'An order is still pending for this symbol.'
        
        assert self.is_connected, 'Not connected.'
        
        assert self.account_number, 'No account number set.'
        
        assert side in SIDE_OF_ORDER_VALUES.values(), \
            'Invalid side: %s' % (side,)
            
        ordertype = kwargs.get('ordertype', ORDER_TYPE_LIMIT)
        assert ordertype in ORDER_TYPE_VALUES.values(), \
            'Invalid order type: %s' % (ordertype,)
            
        tif = kwargs.get('tif', TIME_IN_FORCE_GOOD_TIL_CANCEL)
        assert tif in TIME_IN_FORCE_VALUES.values(), \
            'Invalid time-in-force: %s' % (tif,)
        
        symbol = symbol.strip().upper()
        
        message = Message({
            MESSAGE_TYPE: MESSAGE_TYPE_NEW_ORDER_REQUEST,
            SERVER_ID_KEY: self.serverkey,
            USER_ACCOUNT_NUMBER: self.account_number,
            BROKER_ID: self.mode,
            SYMBOL: symbol,
            SIDE_OF_ORDER: side,
            ORDER_QUANTITY: int(qty),
            ORDER_TYPE: ordertype,
            TIME_IN_FORCE: tif,
            ACCOUNT_TYPE: self.account_type,
            DESTINATION_FOR_ORDER: kwargs.get('destination', self.destination),
        })
        
        if ordertype == ORDER_TYPE_LIMIT:
            assert 'limitprice' in kwargs, \
                'Limit price is required with a limit order.'
        elif ordertype in (ORDER_TYPE_STOP, ORDER_TYPE_STOP_LIMIT):
            assert 'stopprice' in kwargs, \
                'Stop price is required with a stop or stop-limit order.'
                
        if 'limitprice' in kwargs:
            message[LIMIT_PRICE] = Decimal(str(kwargs['limitprice']))
            
        if 'stopprice' in kwargs:
            message[STOP_PRICE] = Decimal(str(kwargs['stopprice']))
        
        order = Order(api=self, symbol=symbol)
        order.request = message
        
        self._pending_orders[symbol] = order
        
        self.push_outgoing(message)
        
        return order

    def buy(self, symbol, qty, block=True, **kwargs):
        order = self.order(SIDE_OF_ORDER_BUY, symbol, qty, **kwargs)
        
        if block:
            order.wait_for_response()
                
        return order
        
    def sell(self, symbol, qty, block=True, **kwargs):
        order = self.order(SIDE_OF_ORDER_SELL, symbol, qty, **kwargs)
        
        if block:
            order.wait_for_response()
                
        return order

if __name__ == '__main__':
    
    # Note, you'll need to acquire a login from the broker.
    api = J2T(mode=MODE_TEST, login=sys.argv[1:3])
    api.connect()
    
    ## Assertions may fail if this is run after market hours.
    
    # Cancel all pending orders.
    for order in api._orders.values():
        if order.is_terminal:
            continue
        order.cancel()
    
    # Place a market order to buy 100 shares of DELL. good for day.
    order1 = api.buy(
        symbol='DELL',
        qty=100,
        ordertype=ORDER_TYPE_MARKET,
        tif=TIME_IN_FORCE_GOOD_FOR_DAY)

    # Place a limit order to buy 1400 shares of ABHD good till cancel
    # at a limit price of 1.00. The order will not be filled.
    # Cancel the order.
    order2 = api.buy(
        symbol='ABHD',
        qty=1400,
        limitprice=1.0,
        ordertype=ORDER_TYPE_LIMIT,
        tif=TIME_IN_FORCE_GOOD_TIL_CANCEL,
        block=False).cancel()
    assert order2.is_filled or order2.is_cancelled
    
    # Place a limit order to buy 750 shares of DELL (any limit price).
    # 500 will be filled. Cancel the order.
    order3 = api.buy(
        symbol='DELL',
        qty=750,
        limitprice=9.76,
        ordertype=ORDER_TYPE_LIMIT,
        tif=TIME_IN_FORCE_GOOD_TIL_CANCEL,
        block=False).cancel()
    assert order3.is_filled or order3.is_cancelled
    
    # Place a market order to buy 3600 shares of ABHD, good for day.
    order4 = api.buy(
        symbol='ABHD',
        qty=3600,
        ordertype=ORDER_TYPE_MARKET,
        tif=TIME_IN_FORCE_GOOD_FOR_DAY).wait_for_completion()
    assert order4.status == ORDER_STATUS_FILLED

    # Disconnect from the trade server.
    api.disconnect()
    