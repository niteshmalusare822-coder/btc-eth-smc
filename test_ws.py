import socketio

sio = socketio.Client(logger=True, engineio_logger=True)

@sio.event
def connect():
    print(">>> connected, joining channel")
    sio.emit("join", "candlestick@B-BTC_USDT_1m")

@sio.on("candlestick")
def on_candle(data):
    print(">>> candlestick event:", data)

@sio.on("new-update")
def on_update(data):
    print(">>> new-update event:", data)

sio.connect("wss://stream.coindcx.com", transports=["websocket"])
sio.wait()
