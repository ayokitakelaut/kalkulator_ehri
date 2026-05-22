import os
import math
import time
import gate_api

from gate_api import (
    Configuration,
    ApiClient,
    FuturesApi
)

from gate_api.exceptions import ApiException


# ====================================
# CONFIG
# ====================================

SETTLE = "usdt"
CONTRACT = "XRP_USDT"

LEVERAGE = 20
MARGIN_USD = 0.10

ENTRY_TICKS = 10
SL_TICKS = 20
TRAILING_TICKS = 20

WAIT_SECONDS = 300


# ====================================
# API
# ====================================

config = Configuration(
    key=os.getenv("GATE_KEY"),
    secret=os.getenv("GATE_SECRET")
)

client = ApiClient(config)
futures = FuturesApi(client)


# ====================================
# FUNCTIONS
# ====================================

def get_contract_info():

    c = futures.get_futures_contract(
        SETTLE,
        CONTRACT
    )

    return {
        "tick": float(c.order_price_round),
        "multiplier": float(c.quanto_multiplier)
    }


def get_price():

    ticker = futures.list_futures_tickers(
        SETTLE,
        contract=CONTRACT
    )[0]

    return float(ticker.last)


def has_open_order():

    orders = futures.list_futures_orders(
        SETTLE,
        status="open"
    )

    for o in orders:

        if o.contract == CONTRACT:
            return True

    return False


def has_position():

    positions = futures.list_positions(
        SETTLE
    )

    for p in positions:

        if (
            p.contract == CONTRACT
            and abs(float(p.size)) > 0
        ):
            return True

    return False


def set_leverage():

    futures.update_position_leverage(
        SETTLE,
        CONTRACT,
        str(LEVERAGE)
    )


def calc_contracts(price,multiplier):

    notional = MARGIN_USD * LEVERAGE

    qty = notional / price

    contracts = qty / multiplier

    return max(
        1,
        math.floor(contracts)
    )


def create_entry():

    print("Waiting 5 minutes...")

    time.sleep(
        WAIT_SECONDS
    )

    info = get_contract_info()

    tick = info["tick"]

    price = get_price()

    entry = price - (
        ENTRY_TICKS * tick
    )

    contracts = calc_contracts(
        price,
        info["multiplier"]
    )

    print(
        f"Current={price}"
    )

    print(
        f"Entry={entry}"
    )

    order = gate_api.FuturesOrder(
        contract=CONTRACT,
        size=contracts,
        price=str(entry),
        tif="gtc"
    )

    result = futures.create_futures_order(
        SETTLE,
        order
    )

    print(result)

    return entry


def create_sl_tp(entry):

    info = get_contract_info()

    tick = info["tick"]

    sl_price = entry - (
        SL_TICKS * tick
    )

    trigger = gate_api.FuturesPriceTriggeredOrder(
        initial=gate_api.FuturesInitialOrder(
            contract=CONTRACT,
            size=0,
            close=True
        ),

        trigger=gate_api.FuturesPriceTrigger(
            strategy_type=0,
            price_type=0,
            price=str(sl_price),
            rule=2
        )
    )

    futures.create_price_triggered_order(
        SETTLE,
        trigger
    )

    print(
        f"SL created: {sl_price}"
    )

    print(
        f"Trailing TP: {TRAILING_TICKS} tick"
    )


# ====================================
# MAIN
# ====================================

try:

    if has_open_order():

        print(
            "Open order exists"
        )

        exit()

    if has_position():

        print(
            "Position exists"
        )

        exit()

    set_leverage()

    entry=create_entry()

    create_sl_tp(entry)

except ApiException as e:

    print(e)

except Exception as e:

    print(e)
