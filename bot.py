import os
import requests
import gate_api

from gate_api import (
    ApiClient,
    Configuration,
    FuturesApi,
    SpotApi,
    FuturesOrder
)

# =====================================================
# CONFIG
# =====================================================

SYMBOL="XRP_USDT"
SETTLE="usdt"

LEVERAGE=30
ENTRY_MARGIN=1

ENTRY_OFFSET_TICK=10
EXIT_OFFSET_TICK=100

MIN_BALANCE=5

NTFY_TOPIC="ALUR"

# =====================================================
# API
# =====================================================

config=Configuration(
    host="https://api.gateio.ws/api/v4",
    key=os.environ["GATE_KEY"],
    secret=os.environ["GATE_SECRET"]
)

client=ApiClient(config)

futures_api=FuturesApi(client)
spot_api=SpotApi(client)

# =====================================================
# NTFY
# =====================================================

def notify(message):

    try:

        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title":"Gate Bot",
                "Priority":"default"
            },
            timeout=15
        )

    except Exception as e:

        print("NTFY ERROR:",e)

# =====================================================
# BALANCE
# =====================================================

def get_spot_balance():

    try:

        accounts=spot_api.list_spot_accounts(
            currency="USDT"
        )

        total=0.0

        for a in accounts:

            try:
                total+=float(a.available)
            except:
                pass

        return total

    except:

        return 0.0


def get_futures_balance():

    try:

        account=futures_api.list_futures_accounts(
            settle=SETTLE
        )

        try:
            return float(account.available)

        except:

            try:
                return float(account.total)

            except:
                return 0.0

    except:

        return 0.0


# =====================================================
# OPEN POSITION
# =====================================================

def has_open_position():

    try:

        positions=futures_api.list_positions(
            settle=SETTLE
        )

        for p in positions:

            if p.contract==SYMBOL:

                try:

                    if abs(float(p.size))>0:
                        return True

                except:
                    pass

    except Exception as e:

        print(e)

    return False


# =====================================================
# OPEN ORDER
# =====================================================

def has_open_order():

    try:

        orders=futures_api.list_futures_orders(
            settle=SETTLE,
            status="open"
        )

        for o in orders:

            if o.contract==SYMBOL:
                return True

    except Exception as e:

        print(e)

    return False


# =====================================================
# MARKET
# =====================================================

def get_contract():

    return futures_api.get_futures_contract(
        settle=SETTLE,
        contract=SYMBOL
    )


def get_price():

    ticker=futures_api.list_futures_tickers(
        settle=SETTLE,
        contract=SYMBOL
    )

    return float(ticker[0].last)


# =====================================================
# LEVERAGE
# =====================================================

def set_leverage():

    try:

        futures_api.update_position_leverage(
            settle=SETTLE,
            contract=SYMBOL,
            leverage=str(LEVERAGE)
        )

        return True

    except Exception as e:

        print(e)

        return False


# =====================================================
# MAIN
# =====================================================

def main():

    logs=[]

    logs.append("=== GATE BOT REPORT ===")

    # -------------------------------------

    spot_balance=get_spot_balance()

    futures_balance=get_futures_balance()

    total_balance=spot_balance+futures_balance

    logs.append(
        f"Spot : ${spot_balance:.4f}"
    )

    logs.append(
        f"Futures : ${futures_balance:.4f}"
    )

    logs.append(
        f"Total : ${total_balance:.4f}"
    )

    # -------------------------------------
    # BALANCE FILTER
    # -------------------------------------

    if total_balance<MIN_BALANCE:

        logs.append("")
        logs.append(
            "STATUS : BALANCE BELOW MINIMUM"
        )

        msg="\n".join(logs)

        print(msg)

        notify(msg)

        return

    # -------------------------------------
    # POSITION FILTER
    # -------------------------------------

    position=has_open_position()

    order=has_open_order()

    logs.append("")
    logs.append(
        f"Open Position : {position}"
    )

    logs.append(
        f"Open Order : {order}"
    )

    if position or order:

        logs.append("")
        logs.append(
            "STATUS : EXISTING TRADE DETECTED"
        )

        msg="\n".join(logs)

        print(msg)

        notify(msg)

        return

    # -------------------------------------
    # PRICE
    # -------------------------------------

    contract=get_contract()

    current=get_price()

    tick=float(
        contract.order_price_round
    )

    entry=current-(tick*ENTRY_OFFSET_TICK)

    stop=entry-(tick*EXIT_OFFSET_TICK)

    trailing=tick*EXIT_OFFSET_TICK

    # -------------------------------------
    # SIZE
    # -------------------------------------

    notional=ENTRY_MARGIN*LEVERAGE

    multiplier=float(
        contract.quanto_multiplier
    )

    size=int(
        notional/
        entry/
        multiplier
    )

    if size<=0:
        size=1

    # -------------------------------------
    # LEVERAGE
    # -------------------------------------

    set_leverage()

    # -------------------------------------
    # CREATE ORDER
    # -------------------------------------

    new_order=FuturesOrder(
        contract=SYMBOL,
        size=size,
        price=str(round(entry,6)),
        tif="gtc"
    )

    result=futures_api.create_futures_order(
        settle=SETTLE,
        futures_order=new_order
    )

    # -------------------------------------
    # REPORT
    # -------------------------------------

    logs.append("")
    logs.append(
        "ENTRY CREATED"
    )

    logs.append(
        f"Current : {current}"
    )

    logs.append(
        f"Entry : {entry}"
    )

    logs.append(
        f"Stop : {stop}"
    )

    logs.append(
        f"Trailing : {trailing}"
    )

    logs.append(
        f"Size : {size}"
    )

    logs.append(
        f"Order ID : {result.id}"
    )

    msg="\n".join(logs)

    print(msg)

    notify(msg)


# =====================================================

if __name__=="__main__":

    try:

        main()

    except Exception as e:

        error=f"BOT ERROR:\n{str(e)}"

        print(error)

        notify(error)
