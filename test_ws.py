import socketio

sio = socketio.Client(logger=True, engineio_logger=False)

CHANNELS = [
    "B-BTC_USDT@trades",
    "B-BTC_USDT@prices",
    "candlestick@B-BTC_USDT_1m",
    "candlestick@B-BTC_USDT_1",
]

@sio.event
def connect():
    print(">>> connected, joining channels", flush=True)
    for ch in CHANNELS:
        sio.emit("join", ch)
        print(f">>> joined {ch}", flush=True)

@sio.on("*")
def catch_all(event, data):
    print(f">>> EVENT NAME: {event}", flush=True)
    print(f">>> DATA: {data}", flush=True)

sio.connect("wss://stream.coindcx.com", transports=["websocket"])
sio.wait()
