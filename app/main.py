import asyncio
import dataclasses
import datetime
import json
import logging
import os
import typing

import eopr
from dotenv import load_dotenv
from eopr.core.indicators import macd, rsi
from eopr.core.strategies import macd_rsi_crossover
from eopr.utils import candle_parser
from litestar import Litestar, WebSocket, websocket_listener
from websocket._app import WebSocketApp

logger = logging.getLogger("uvicorn")

dotenv = load_dotenv()
if not dotenv:
    raise ValueError("dotenv not loaded")

eo_url = os.getenv("EO_URL")
eo_token = os.getenv("EO_TOKEN")
eo_asset_id = os.getenv("EO_ASSET_ID")
eo_device_token = os.getenv("EO_DEVICE_TOKEN")

try:
    assert eo_url is not None and eo_url != ""
    assert eo_token is not None and eo_token != ""
    assert eo_asset_id is not None and eo_asset_id != ""
    assert eo_device_token is not None and eo_device_token != ""
except AssertionError as assert_err:
    raise ValueError("Please set the EO environment variables") from assert_err

CandleSeries = list[dict[str, float | list[float]]]
CandleExpTimes = list[list[int | list[list[float | int]]]]
CandleMessage = dict[str, int | CandleSeries | CandleExpTimes]
CandleData = dict[str, str | CandleMessage]


@dataclasses.dataclass
class Signal:
    """A signal for a buy or sell action.

    Attributes:
        buy (bool): True if a buy signal, False otherwise.
        sell (bool): True if a sell signal, False otherwise.
    """

    buy: bool
    sell: bool


@dataclasses.dataclass
class CandleChartContainer:
    """A container for candle chart data.

    Attributes:
        candles (list[float]): The candle chart data.
        signal (Signal): The signal for a buy or sell action.
        strike_time (datetime.date): The strike time.
        expiration_time (datetime.date): The expiration time.
    """

    candles: list[CandleData]
    signal: Signal
    strike_time: datetime.date | None = None
    expiration_time: datetime.date | None = None


WsCallback = typing.Callable[[CandleChartContainer, rsi.RSIParameters], None]


def analyze_candles(
    chart_container: CandleChartContainer,
    rsi_params: rsi.RSIParameters,
    callback: WsCallback,
) -> None:
    candles: list[list[float]] = []
    for candle_datum in chart_container.candles:
        candles.append(candle_parser.parse_candles_data(candle_datum))

    rsi_params.prices = candles
    rsi_ = rsi.rsi(rsi_params)
    rsi_.overbought = 70
    rsi_.oversold = 30
    macd_params = macd.MACDParameters(
        prices=candles,
        fast=12,
        slow=26,
        signal=9,
    )
    macd_ = macd.macd(macd_params)
    trade_signal = macd_rsi_crossover.trade(rsi_, macd_)
    chart_container.signal.buy = trade_signal.buy
    chart_container.signal.sell = trade_signal.sell

    callback(chart_container, rsi_params)


def message_strategy(
    ws: WebSocketApp,
    message: bytes,
    chart_container: CandleChartContainer,
    rsi_params: rsi.RSIParameters,
    callback: WsCallback,
) -> None:
    parsed_msg = json.loads(message)
    if parsed_msg["action"] == "candles":
        chart_container.candles.append(parsed_msg)

        # Prevent the list from growing too large
        if len(chart_container.candles) >= (rsi_params.period * 3):
            chart_container.candles = chart_container.candles[rsi_params.period - 1 :]

    analyze_candles(chart_container, rsi_params, callback)


def init_eo_session(
    chart_container: CandleChartContainer,
    rsi_params: rsi.RSIParameters,
    callback: WsCallback,
):
    def on_message_strategy(ws: WebSocketApp, message: bytes) -> None:
        return message_strategy(ws, message, chart_container, rsi_params, callback)

    try:
        eopr.read(
            eopr.ReaderParams(
                url=eo_url,
                token=eo_token,
                device_token=eo_device_token,
                asset_id=int(eo_asset_id),
                on_message_strategy=on_message_strategy,
            )
        )
    except Exception as err:
        logger.error(err)


def send_json(
    socket: WebSocket[typing.Any, typing.Any, typing.Any],
    data: str,
    chart_container: CandleChartContainer,
    rsi_params: rsi.RSIParameters,
):
    asyncio.run(
        socket.send_json(
            {
                "message": data,
                "chart_container": chart_container,
                "rsi_params": rsi_params,
            }
        )
    )


@websocket_listener("/")
def handler(data: str, socket: WebSocket[typing.Any, typing.Any, typing.Any]):
    signal = Signal(buy=False, sell=False)
    chart_container = CandleChartContainer(
        signal=signal, candles=[], strike_time=None, expiration_time=None
    )
    rsi_params = rsi.RSIParameters(prices=[], period=14)

    def callback(
        chart_container: CandleChartContainer, rsi_params: rsi.RSIParameters
    ) -> None:
        return send_json(socket, data, chart_container, rsi_params)

    init_eo_session(chart_container, rsi_params, callback)

    return data


app = Litestar([handler])
