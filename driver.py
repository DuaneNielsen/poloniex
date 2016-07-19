#! python3

from autobahn.asyncio.wamp import ApplicationSession
from autobahn.asyncio.wamp import ApplicationRunner
from asyncio import coroutine
from ast import literal_eval
from mm import MM
import time 
import json
import sys
import signal
import decimal


class PoloniexComponent(ApplicationSession):


    apikey = 
    secret = 
    LAST = 1
    ASK = 2
    BID = 3

    mm = MM('mm',apikey,secret,'USDT_ETH');
    
    def onConnect(self):
        self.join(self.config.realm)
        self.mm.connect()
        print ('waiting for data')

    @coroutine
    def onJoin(self, details):
        def onTicker(*args):
            #print("Ticker event received:", args)
            if args[0] == 'USDT_ETH':
                print("Ticker event received:", args)
                self.mm.tick(bid=args[self.BID],ask=args[self.ASK])
                print(self.mm.state)
                
        try:
            yield from self.subscribe(onTicker, 'ticker')
        except Exception as e:
            print("Could not subscribe to topic:", e)
    

def signal_handler(signal, frame):
        print('You pressed Ctrl+C!')
        PoloniexComponent.mm.cancel_bid(None)
        sys.exit(0)

            
def main():
    signal.signal(signal.SIGINT, signal_handler)
    runner = ApplicationRunner("wss://api.poloniex.com:443", "realm1")
    runner.run(PoloniexComponent)


if __name__ == "__main__":
    main()