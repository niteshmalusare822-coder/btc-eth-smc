import socketio

sio = socketio.Client(logger=True, engineio_logger=False)

@sio.event
def connect():
    print(">>> connected, joining channel", flush=True)
    sio.emit("join", "candlestick@B-BTC_USDT_1m")

@sio.on("*")
def catch_all(event, data):
    print(f">>> EVENT NAME: {event}", flush=True)
    print(f">>> DATA: {data}", flush=True)

sio.connect("wss://stream.coindcx.com", transports=["websocket"])
sio.wait()
