def post_worker_init(worker):
    from app import start_live_ws_once
    start_live_ws_once()
