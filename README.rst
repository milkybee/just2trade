=======================================================================
just2trade - Python wrapper around the Just2Trade stock trading API
=======================================================================

Overview
========

Provides Pythonic access to the Just2Trade trading API.

Supports most features documented at http://www.just2trade.com/trading_tools/api.

**This software is not developed, sponsored or supported by Just2Trade
in any way.**

**Do not contact Just2Trade with questions about this software.**

If you see a bug or problem with the code, please submit an issue at
https://github.com/milkybee/just2trade.

**This software has no warranty and is provided "as is". It is your
responsibility to validate the behavior of the routines and their accuracy
using the source code provided. The author is not responsible for any loss,
financial or otherwise, as a result of using this software.**

Installation
------------

Ensure you have pip installed. Then, from a console, run:

::

    sudo pip install -U https://github.com/milkybee/just2trade/tarball/master

Usage
-----

Acquire a trading account and place your username and password in the file
`~/.just2trade`, one line per each value, like:

::

    username
    password

Set the file to be accessible only by you with:

::

    chmod 600 ~/.just2trade

Import and initialize the API via:

::

    from just2trade import *
    api = J2T()
    api.connect()
    print 'account number:', api.account_number
    print 'margin balance:', api.account[MARGIN_TRADE_BALANCE]
    print 'cash balance:', api.account[CASH_TRADE_BALANCE]

The api.connect() method starts a thread that asynchronously sends and receives
messages from the API server. It blocks until some basic reporting messages are
received.

To place a market order to buy 100 shares of DELL, good for day:

::

    order = api.buy(
        symbol='DELL',
        qty=100,
        ordertype=ORDER_TYPE_MARKET,
        tif=TIME_IN_FORCE_GOOD_FOR_DAY)
    print order.order_id


To place a limit order to buy 750 shares of DELL at $9.76 a share,
and then cancel the order:

::

    order = api.buy(
        symbol='DELL',
        qty=750,
        limitprice=9.76,
        ordertype=ORDER_TYPE_LIMIT,
        tif=TIME_IN_FORCE_GOOD_TIL_CANCEL)
    order.cancel()

The default behavior of api.buy() is to block until an initial response
is received from the API server. However, the order may not be immediately
filled, if ever.

As long as your process is running, the IO thread will
eventually receive messages from the server, indicating order fullfillment.

You can asynchronously check for this completion like:

::

    order.status == ORDER_STATUS_FILLED
    
Or you can synchronously check, blocking until the order is filled via:

::

    order.wait_for_completion()

When you're done trading and have received all updates from the API server, you can cleanly disconnect via:

::

    api.disconnect()
    