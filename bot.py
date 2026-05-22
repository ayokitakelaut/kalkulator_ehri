import os
import random
import requests
from gate_api import Configuration, ApiClient

# =====================================
# DEMO API
# =====================================

GATE_KEY=os.getenv(
    "GATE_KEY",
    ""
)

GATE_SECRET=os.getenv(
    "GATE_SECRET",
    ""
)

config=Configuration(
    host="https://api.gateio.ws/api/v4",
    key=GATE_KEY,
    secret=GATE_SECRET
)

client=ApiClient(config)

# =====================================
# STRATEGY
# =====================================

SYMBOL="XRP_USDT"

INITIAL_BALANCE=5.0
balance=INITIAL_BALANCE

ENTRY_MARGIN=0.10
LEVERAGE=100

ENTRY_TICK=10
TP_TICK=20
SL_TICK=20

TICK=0.0001
FEE_RATE=0.0004

NTFY_TOPIC="ALUR"

trade_count=0
win_count=0
loss_count=0

# =====================================
# NTFY
# =====================================

def notify(message):

    try:

        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            timeout=10
        )

    except Exception as e:

        print(
            "Notify Error:",
            e
        )

# =====================================
# PRICE
# =====================================

def get_price():

    try:

        r=requests.get(
            "https://api.gateio.ws/api/v4/futures/usdt/tickers",
            timeout=10
        )

        data=r.json()

        for item in data:

            if item["contract"]==SYMBOL:

                return float(
                    item["last"]
                )

    except Exception as e:

        print(
            "Price Error:",
            e
        )

    return 1.40


# =====================================
# SIMULATION
# =====================================

def simulate_trade():

    current=get_price()

    entry=current-(ENTRY_TICK*TICK)

    tp=entry+(TP_TICK*TICK)

    sl=entry-(SL_TICK*TICK)

    position=ENTRY_MARGIN*LEVERAGE

    amount=position/entry

    fee=position*FEE_RATE

    simulated_move=random.randint(
        -50,
        50
    )

    simulated_price=entry+(
        simulated_move*TICK
    )

    pnl=0
    result=""

    if simulated_price>=tp:

        result="WIN"

        pnl=amount*(
            tp-entry
        )

    elif simulated_price<=sl:

        result="LOSS"

        pnl=amount*(
            sl-entry
        )

    else:

        result="OPEN"

        pnl=amount*(
            simulated_price-entry
        )

    pnl-=fee

    return {

        "current":current,
        "entry":entry,
        "tp":tp,
        "sl":sl,
        "position":position,
        "amount":amount,
        "fee":fee,
        "result":result,
        "pnl":pnl,
        "simulated_price":simulated_price

    }


# =====================================
# MAIN
# =====================================

def main():

    global balance
    global trade_count
    global win_count
    global loss_count

    trade=simulate_trade()

    trade_count+=1

    if trade["result"]=="WIN":

        win_count+=1

    elif trade["result"]=="LOSS":

        loss_count+=1

    balance+=trade["pnl"]

    win_rate=0

    if trade_count>0:

        win_rate=(
            win_count/
            trade_count
        )*100


    report=[]

    report.append(
        "=== GATE XRP SIMULATOR ==="
    )

    report.append("")

    if GATE_KEY:

        report.append(
            f"Demo API: {GATE_KEY[:4]}****"
        )

    else:

        report.append(
            "Demo API: Not configured"
        )

    report.append("")

    report.append(
        f"Trade: {trade_count}"
    )

    report.append(
        f"Balance: ${balance:.4f}"
    )

    report.append(
        "(balance hanya pelaporan)"
    )

    report.append("")

    report.append(
        f"Margin: ${ENTRY_MARGIN}"
    )

    report.append(
        f"Leverage: {LEVERAGE}x"
    )

    report.append(
        f"Position: ${trade['position']:.2f}"
    )

    report.append(
        f"XRP Size: {trade['amount']:.4f}"
    )

    report.append("")

    report.append(
        f"Current: {trade['current']:.4f}"
    )

    report.append(
        f"Entry: {trade['entry']:.4f}"
    )

    report.append(
        f"TP: {trade['tp']:.4f}"
    )

    report.append(
        f"SL: {trade['sl']:.4f}"
    )

    report.append(
        f"Simulated Price: {trade['simulated_price']:.4f}"
    )

    report.append("")

    report.append(
        f"Fee: ${trade['fee']:.5f}"
    )

    report.append(
        f"Result: {trade['result']}"
    )

    report.append(
        f"PnL: ${trade['pnl']:.5f}"
    )

    report.append("")

    report.append(
        f"Wins: {win_count}"
    )

    report.append(
        f"Losses: {loss_count}"
    )

    report.append(
        f"Win Rate: {win_rate:.2f}%"
    )

    text="\n".join(
        report
    )

    print(text)

    notify(text)


if __name__=="__main__":

    main()
