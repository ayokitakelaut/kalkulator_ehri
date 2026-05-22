import os
import requests
import gate_api

from gate_api import (
    ApiClient,
    Configuration,
    FuturesApi,
    SpotApi,
    FuturesOrder,
)

# =========================================================
# CONFIG
# =========================================================

SYMBOL = "XRP_USDT"
SETTLE = "usdt"

LEVERAGE = 30
ENTRY_MARGIN = 1

ENTRY_OFFSET_TICK = 10
EXIT_OFFSET_TICK = 100

MIN_BALANCE = 5

NTFY_TOPIC = "ALUR"

# =========================================================
# API
# =========================================================

config = Configuration(
    host="https://api.gateio.ws/api/v4",
    key=os.environ["GATE_KEY"],
    secret=os.environ["GATE_SECRET"]
)

client = ApiClient(config)

futures_api = FuturesApi(client)
spot_api = SpotApi(client)

# =========================================================
# NTFY
# =========================================================

def notify(message):

    try:

        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": "Gate Bot",
                "Priority": "default"
            },
            timeout=15
        )

    except Exception as e:
        print("NTFY ERROR:", e)

# =========================================================
# BALANCE
# =========================================================

def get_spot_balance():

    accounts = spot_api.list_spot_accounts(
        currency="USDT"
    )

    total = 0.0

    for a in accounts:
        total += float(a.available)

    return total


def get_futures_balance():

    accounts = futures_api.list_futures_accounts(
        settle=SETTLE
    )

    total = 0.0

    for a in accounts:
        total += float(a.available)

    return total

# =========================================================
# OPEN POSITION / ORDER
# =========================================================

def has_open_position():

    positions = futures_api.list_positions(
        settle=SETTLE
    )

    for p in positions:

        if p.contract == SYMBOL:

            if abs(float(p.size)) > 0:
                return True

    return False


def has_open_order():

    orders = futures_api.list_futures_orders(
        settle=SETTLE,
        status="open"
    )

    for o in orders:

        if o.contract == SYMBOL:
            return True

    return False

# =========================================================
# MARKET DATA
# =========================================================

def get_contract():

    return futures_api.get_futures_contract(
        settle=SETTLE,
        contract=SYMBOL
    )


def get_price():

    ticker = futures_api.list_futures_tickers(
        settle=SETTLE,
        contract=SYMBOL
    )

    return float(ticker[0].last)

# =========================================================
# LEVERAGE
# =========================================================

def set_leverage():

    futures_api.update_position_leverage(
        settle=SETTLE,
        contract=SYMBOL,
        leverage=str(LEVERAGE)
    )

# =========================================================
# MAIN
# =========================================================

def main():

    logs = []

    logs.append("=== GATE BOT REPORT ===")

    # -----------------------------------------------------

    spot_balance = get_spot_balance()
    futures_balance = get_futures_balance()

    total_balance = spot_balance + futures_balance

    logs.append(f"Spot Balance    : ${spot_balance:.4f}")
    logs.append(f"Futures Balance : ${futures_balance:.4f}")
    logs.append(f"Total Balance   : ${total_balance:.4f}")

    # -----------------------------------------------------
    # SAFETY FILTER
    # -----------------------------------------------------

    if total_balance < MIN_BALANCE:

        logs.append("")
        logs.append("STATUS : BALANCE BELOW MINIMUM")
        logs.append("TRADE CANCELLED")

        message = "\n".join(logs)

        print(message)

        notify(message)

        return

    # -----------------------------------------------------
    # SINGLE POSITION RULE
    # -----------------------------------------------------

    open_position = has_open_position()
    open_order = has_open_order()

    logs.append("")
    logs.append(f"Open Position : {open_position}")
    logs.append(f"Open Order    : {open_order}")

    if open_position or open_order:

        logs.append("")
        logs.append("STATUS : EXISTING POSITION/ORDER DETECTED")
        logs.append("SKIP TRADE")

        message = "\n".join(logs)

        print(message)

        notify(message)

        return

    # -----------------------------------------------------
    # MARKET INFO
    # -----------------------------------------------------

    contract = get_contract()

    current_price = get_price()

    tick = float(contract.order_price_round)

    entry_price = current_price - (tick * ENTRY_OFFSET_TICK)

    stop_price = entry_price - (tick * EXIT_OFFSET_TICK)

    trailing_distance = tick * EXIT_OFFSET_TICK

    # -----------------------------------------------------
    # POSITION SIZE
    # -----------------------------------------------------

    notional = ENTRY_MARGIN * LEVERAGE

    multiplier = float(contract.quanto_multiplier)

    size = int(
        notional /
        entry_price /
        multiplier
    )

    if size <= 0:
        size = 1

    # -----------------------------------------------------
    # LEVERAGE
    # -----------------------------------------------------

    set_leverage()

    logs.append("")
    logs.append("Leverage Updated")

    # -----------------------------------------------------
    # CREATE ENTRY
    # -----------------------------------------------------

    order = FuturesOrder(
        contract=SYMBOL,
        size=size,
        price=str(round(entry_price, 6)),
        tif="gtc"
    )

    result = futures_api.create_futures_order(
        settle=SETTLE,
        futures_order=order
    )

    # -----------------------------------------------------
    # REPORT
    # -----------------------------------------------------

    logs.append("")
    logs.append("=== ENTRY CREATED ===")

    logs.append(f"Symbol            : {SYMBOL}")
    logs.append(f"Current Price     : {current_price}")
    logs.append(f"Tick Size         : {tick}")

    logs.append(f"Entry Offset Tick : {ENTRY_OFFSET_TICK}")
    logs.append(f"Entry Price       : {entry_price}")

    logs.append(f"Leverage          : {LEVERAGE}x")
    logs.append(f"Margin            : ${ENTRY_MARGIN}")

    logs.append(f"Position Size     : {size}")

    logs.append("")
    logs.append("=== EXIT RULE ===")

    logs.append(f"Trailing Distance : {trailing_distance}")
    logs.append(f"Stop Loss Price   : {stop_price}")

    logs.append("")
    logs.append("=== ORDER RESULT ===")

    logs.append(f"Order ID : {result.id}")
    logs.append(f"Status   : {result.status}")

    message = "\n".join(logs)

    print(message)

    notify(message)

# =========================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as e:

        error_msg = f"BOT ERROR:\n{str(e)}"

        print(error_msg)

        notify(error_msg)
