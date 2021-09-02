from unicorn_binance_websocket_api.unicorn_binance_websocket_api_manager import BinanceWebSocketApiManager
from traderboard.models import TradingAccount
from traderboard.tasks import record_trade, record_transaction
import logging
import time
import threading
import json
import os


logging.basicConfig(level=logging.DEBUG,
                    filename=os.path.basename(__file__) + '.log',
                    format="{asctime} [{levelname:8}] {process} {thread} {module}: {message}",
                    style="{")


def print_stream_buffer_data(binance_websocket_api_manager, stream_id):
    while True:
        if binance_websocket_api_manager.is_manager_stopping():
            exit(0)
        oldest_stream_data_from_stream_buffer = binance_websocket_api_manager.pop_stream_data_from_stream_buffer(stream_id)
        if oldest_stream_data_from_stream_buffer is False:
            time.sleep(0.01)
        else:
            ta_id = int(binance_websocket_api_manager.get_stream_label(stream_id))
            event = json.loads(oldest_stream_data_from_stream_buffer)
            if event['e'] == 'balanceUpdate':
                record_transaction(event, ta_id)
            elif event['e'] == "executionReport" and event['X'] == "TRADE":
                record_trade(event, ta_id)
            print(oldest_stream_data_from_stream_buffer)


def update_streams(binance_websocket_api_manager):
    ta_labels = set([str(ta.id) for ta in TradingAccount.objects.all()])
    active_streams = binance_websocket_api_manager.get_active_stream_list()
    if active_streams:
        active_stream_labels = set([active_streams[stream_id]['stream_label'] for stream_id in active_streams.keys()])
        streams_to_delete = map(lambda x: x['stream_id'], 
                                filter(lambda x: x['stream_label'] in set(active_stream_labels - ta_labels), 
                                    active_streams.values()
                                )
                            )
        streams_to_create = ta_labels - active_stream_labels 

    else:
        streams_to_delete = set([])
        streams_to_create = ta_labels

    for stream_id in streams_to_delete:
        # delete the userData streams
        binance_websocket_api_manager.delete_stream_from_stream_list(stream_id)

    for stream_label in streams_to_create:
        # create the userData streams
        ta = TradingAccount.objects.get(id=stream_label)
        ta_stream_id = binance_websocket_api_manager.create_stream('arr', 
                                                                   '!userData', 
                                                                    stream_label=str(ta.id),
                                                                    stream_buffer_name=True,
                                                                    api_key=ta.api_key, 
                                                                    api_secret=ta.api_secret)
        # start a worker process to move the received stream_data from the stream_buffer to a print function
        worker_thread = threading.Thread(target=print_stream_buffer_data, args=(binance_websocket_api_manager,
                                                                                ta_stream_id))
        worker_thread.start()


def run():
    # create instances of BinanceWebSocketApiManager
    binance_com_websocket_api_manager = BinanceWebSocketApiManager(exchange="binance.com")

    while True:
        update_streams(binance_com_websocket_api_manager)
        binance_com_websocket_api_manager.print_summary()
        time.sleep(10)