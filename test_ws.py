import socketio

sio = socketio.Client(logger=True, engineio_logger=False)

@sio.event
def connect():
    print(">>> connected, joining channels", flush=True)
    sio.emit('join', {'channelName': 'B-BTC_USDT_1m-futures'})
    sio.emit('join', {'channelName': 'B-BTC_USDT@trades-futures'})

@sio.on('candlestick')
def on_candle(response):
    print(f">>> CANDLESTICK: {response}", flush=True)

@sio.on('new-trade')
def on_trade(response):
    print(f">>> TRADE: {response}", flush=True)

sio.connect("wss://stream.coindcx.com", transports=["websocket"])
sio.wait()
