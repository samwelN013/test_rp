from pybit.unified_trading import WebSocket
from time import sleep

ws = WebSocket(
    testnet=False, # it must be false
    channel_type="linear",
)


def handle_message(message):
    print(message)


ws.trade_stream(symbol="ADAUSDT", callback=handle_message   )

while True:
    sleep(1)
