#! python3

from autobahn.asyncio.wamp import ApplicationSession
from autobahn.asyncio.wamp import ApplicationRunner
from asyncio import coroutine
from ast import literal_eval
import time 
import json
import sys
import decimal
import uuid


class PoloniexComponent(ApplicationSession):
    prices = {}
    pricesX = {}
    f = open('workfile','a')
    arb_btc_eth_usd = ()
    triangles = {}
    LAST = 1
    ASK = 2
    BID = 3
    TAKER_FEE = 1.0025
    TAKER_FEE_INV = 0.9975
    

    def onConnect(self):
        self.join(self.config.realm)
        
        print ('waiting for data')

    @coroutine
    def onJoin(self, details):
        def onTicker(*args):
           self.prices[args[0]] = args

           #self.triangle('USD_BTC_ETH','USDT_BTC', 'USDT_ETH','BTC_ETH')
           #self.triangle('USD_XRM_LTC','USDT_XMR','USDT_LTC','XMR_LTC')
           #self.triangle('USD_BTC_LTC','USDT_BTC','USDT_LTC','BTC_LTC')
           #print("Ticker event received:", args)
           self.writeSpread(args[0])
        try:
            yield from self.subscribe(onTicker, 'ticker')
        except Exception as e:
            print("Could not subscribe to topic:", e)

            
    def writeSpread(self, pair):
        uid = uuid.uuid1()
        ask = float(self.prices[pair][self.ASK]) 
        bid = float(self.prices[pair][self.BID])
        spread = ask - bid
        self.pricesX[pair] = (uid.hex,) + self.prices[pair] + (spread,)
        print (self.pricesX[pair])
        self.f.write(str(self.pricesX[pair]) + "\n" )
        self.f.flush()

    def triangle(self, name, base2, base1, cross):
        if base2 in self.prices and base1 in self.prices and cross in self.prices:
            
            # bid asks adjusted with fees
            
            base1_ask = float(self.prices[base1][self.ASK]) * self.TAKER_FEE
            base2_ask = float(self.prices[base2][self.ASK]) * self.TAKER_FEE        
            cross_ask = float(self.prices[cross][self.ASK]) * self.TAKER_FEE
 
            base1_bid = float(self.prices[base1][self.BID]) * self.TAKER_FEE_INV
            base2_bid = float(self.prices[base2][self.BID]) * self.TAKER_FEE_INV
            cross_bid = float(self.prices[cross][self.BID]) * self.TAKER_FEE_INV
            
            #quote_bids = (base1_bid, base2_bid, cross_bid)
            #quote_asks = (base1_ask, base2_ask, cross_ask)
            
            #print (name)
            #print (quote_bids)
            #print (quote_asks)
            
            arb = (base2_bid * cross_bid) - base1_ask
            carb = (base1_bid /cross_ask) - base2_ask
            
            arb_t = (arb, base1_ask, base2_bid, cross_bid, base1, cross, base2)
            carb_t = (carb, base2_ask, base1_bid, cross_ask, base2, cross, base1)
            
            self.update (name + "_straight",arb_t)

            self.update (name + "_counter",carb_t)
            
            #self.update(name, arb_t)
    
    def update(self, name, arb_t):
        if name in self.triangles:
            last = self.triangles[name]
            if last != arb_t:
                
                self.triangles[name] = arb_t
                #print (time.strftime("%X"),name, self.triangles[name])
                if arb_t[0] > 0:
                    print (time.strftime("%X"),name, self.triangles[name])
                elif last[0] > 0 and arb_t[0] <= 0:
                    print (time.strftime("%X"),name,"closed")
        else:
            self.triangles[name] = arb_t
            print ("INIT",name, self.triangles[name])
    
            
def main():
    runner = ApplicationRunner("wss://api.poloniex.com:443", "realm1")
    runner.run(PoloniexComponent)


if __name__ == "__main__":
    main()