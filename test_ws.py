import socketio

sio = socketio.Client(logger=True, engineio_logger=False)

CHANNELS = [
    "B-BTC_USDT_1m-futures",
    "B-BTC_USDT_1h-futures",
]

@sio.event
def connect():
    print(">>> connected, joining channels", flush=True)
    for ch in CHANNELS:
        sio.emit("join", {"channelName": ch})
        print(f">>> joined {ch}", flush=True)

@sio.on("candlestick")
def candlestick(data):
    print(f">>> CANDLESTICK: {data}", flush=True)

@sio.on("*")
def catch_all(event, data):
    print(f">>> EVENT NAME: {event}", flush=True)
    print(f">>> DATA: {data}", flush=True)

sio.connect("wss://stream.coindcx.com", transports=["websocket"])
sio.wait()
