import json
import time
import requests

from datetime import date, datetime, timedelta
from collections import namedtuple
from typing import Callable, Iterator, Any
from termcolor import colored
from requests_cache import CachedSession


session = CachedSession(
    cache_name="coinbase_cache",
    backend="filesystem",
    use_cache_dir=True,
    expire_after=timedelta(days=365),
)
RATE_LIMIT_SECS = 1.0

Result = namedtuple(
    "Result",
    "coin, date, price, wallet, wallet_value, investment, fees, invested, fee, diff, diff_pct",
)


def get_price(coin: str, date: date) -> dict:
    url = f"https://api.coinbase.com/v2/prices/{coin}-USD/spot?currency=USD&date={date:%Y-%m-%d}"
    resp = session.get(url)
    if not resp.from_cache:
        time.sleep(RATE_LIMIT_SECS)
    return resp.json()


def get_historical_prices(
    coin: str, start: date, end: date, increment_days: int
) -> Iterator[tuple[date, dict]]:
    curr_day = start
    while curr_day <= end:
        yield curr_day, get_price(coin, curr_day)
        curr_day += timedelta(days=increment_days)


def daily_investment(
    coin: str,
    starting_balance: float,
    daily_buy: float,
    fee: float,
    start: date,
    end: date,
    increment_days: int,
) -> Iterator[Result]:
    wallet: float = starting_balance
    investment: float = 0
    fees: float = 0

    next_vested_day = start
    for date, info in get_historical_prices(coin, start, end, 1):
        price = float(info["data"]["amount"])

        invested = 0
        if next_vested_day == date:
            invested = daily_buy
            investment += invested
            fees += fee
            wallet += (invested - fee) / price

            next_vested_day += timedelta(days=increment_days)

        wallet_value = wallet * price
        diff = wallet_value - investment
        diff_pct = (diff / investment) * 100.0

        yield Result(
            coin,
            date,
            price,
            wallet,
            wallet_value,
            investment,
            fees,
            invested,
            fee if invested else 0,
            diff,
            diff_pct,
        )


def print_daily_investment(func: Callable[..., Result]):
    last: Result = None
    for idx, r in enumerate(func()):
        if idx % 25 == 0:
            header = f"{r.coin:15}|{'Price':>10} |{'Balance':>10} |{'CASH':>10} |{'Fees':>10} |{'Diff($)':>10} |{'Diff(%)':>10} |{' Coin Amount':34}| {'Coin Value':34}"
            print(colored(header, "white", "on_blue", attrs=["bold"]))

        price = colored(
            f"{r.price:10,.2f}", "red" if last and last.price > r.price else "green"
        )
        balance = colored(
            f"{r.wallet_value:10,.2f}",
            "red" if r.investment > r.wallet_value else "green",
        )
        investment = f"{r.investment:10,.0f}" if r.invested else f"{'':10}"
        fees = colored(f"{r.fees:10,.2f}", "red") if r.fee else f"{'':10}"
        diff = colored(f"{r.diff:10.2f}", "red" if r.diff < 0 else "green")
        diff_pct = colored(f"{r.diff_pct:9.0f}%", "red" if r.diff_pct < 0 else "green")
        wallet_balance = colored(
            f"${r.wallet * r.price:,.2f}",
            "red" if last and last.price > r.price else "green",
        )

        amount = (r.invested - r.fee) / r.price
        coin_amount = (
            f" = {last.wallet:.6f} + {amount:.6f}" if last and amount else f"{'':23}"
        )
        coin_value = (
            f" = {last.wallet * r.price:,.2f} + {amount * r.price:.2f}"
            if last and amount
            else ""
        )
        print(
            f"{r.date:%Y-%m-%d %a} |{price} |{balance} |{investment} |"
            + f"{fees} |{diff} |{diff_pct} | "
            + f"{r.wallet:.6f}{coin_amount} | "
            + f"{wallet_balance}{coin_value}"
        )
        last = r


today = datetime.today()
epoch = today - timedelta(days=270 * 1)
print_daily_investment(lambda: daily_investment("ETH", 0, 50, 1.99, epoch, today, 7))

# daily_investment("BTC", 0, 50, 1.99, epoch, today, 7)
