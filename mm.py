from transitions.extensions import LockedMachine as Machine
from threading import Thread
import time
from api import poloniex
from retrying import retry

class MM(object):

    states = ['INIT','BID_SEARCH','BID_SENDING','BID_WAIT_CONFIRM','BID_PLACED','BID_CANCELLING','BID_LIQUIDATING',
        'ASK_SEARCH','ASK_SENDING','ASK_WAIT_CONFIRM','ASK_PLACED','ASK_CANCELLING']
    
    def __init__(self, name, APIKey, Secret, currency_pair):
        self.name = name
        self.polo = poloniex(APIKey,Secret)
        self.currency_pair = currency_pair
        
        self.machine = Machine(model=self, states=MM.states, initial='INIT', send_event=True, ignore_invalid_triggers=True)
        
        #parameters
        self.risk = float(0)
        self.bid_delta      = 0.0000001  # the amount to repost order when you are too high or low
        self.bid_increments = 0.00000001 # the amount to outbid the highest bid by
        self.amount = 0.001
        
        #setup values
        self.bid = float(0)
        self.ask = float(0)
        
        self.bid_waiting_at = float(0)
        self.bid_order = None
        self.bid_position = float(0)
        
        self.ask_waiting_at = float(0)
        self.ask_order = None
        self.ask_position = float(0)
        
        #self.result = {}
        
        #main trading loop
        self.machine.add_transition(trigger='connect', source='INIT', dest='BID_SEARCH')
        
        # bid
        self.machine.add_transition(trigger='tick', source='BID_SEARCH', dest='BID_SENDING',prepare='set_tick',conditions='found_bid')
        
        self.machine.on_enter_BID_SENDING('retry_place_bid')
        self.machine.add_transition(trigger='try_place_bid', source='BID_SENDING', dest='BID_WAIT_CONFIRM', conditions='bid_placed')
        
        self.machine.on_enter_BID_WAIT_CONFIRM('retry_bid_confirm')
        self.machine.add_transition(trigger='try_confirm_bid', source='BID_WAIT_CONFIRM', dest='BID_PLACED',conditions='inBidOrder')
        
        self.machine.on_enter_BID_PLACED('retry_bid_executed')
        self.machine.add_transition(trigger='try_bid_executed', source='BID_PLACED', dest='ASK_SEARCH', conditions='bid_executed')
        
        # ask
        self.machine.add_transition(trigger='tick', source='ASK_SEARCH', dest='ASK_SENDING', prepare='set_tick',conditions='found_ask')
        self.machine.on_enter_ASK_SENDING('retry_place_ask')
        self.machine.add_transition(trigger='place_ask', source='ASK_SENDING', dest='ASK_WAIT_CONFIRM', conditions='ask_placed')
        self.machine.on_enter_ASK_WAIT_CONFIRM('retry_ask_placed')
        self.machine.add_transition(trigger='ask_placed', source='ASK_WAIT_CONFIRM', dest='ASK_PLACED',conditions='isInAskOrderbook')
        self.machine.on_enter_ASK_PLACED('retry_ask_executed')
        self.machine.add_transition(trigger='ask_executed', source='ASK_PLACED', dest='BID_SEARCH', conditions='ask_executed')
        
        #reposition bids
        self.machine.add_transition(trigger='tick', source='BID_PLACED', dest='BID_CANCELLING', prepare='set_tick', conditions='bid_out_of_range')
        self.machine.on_enter_BID_CANCELLING('retry_cancel_bid')
        self.machine.add_transition(trigger='post_cancel_bid', source='BID_CANCELLING', dest='BID_SEARCH', conditions='cancel_bid')
        
        self.machine.add_transition(trigger='tick_abort', source='ASK_SEARCH', dest='BID_LIQUIDATING')
        self.machine.add_transition(trigger='order_executed', source='BID_LIQUIDATING', dest='BID_SEARCH')
        self.machine.add_transition(trigger='tick_abort', source='ASK_PLACED', dest='ASK_CANCELLING')
        self.machine.add_transition(trigger='order_executed', source='ASK_CANCELLING', dest='ASK_SEARCH')
        
        # need to figure out cleanup mechanism on shutdown
        #self.machine.add_transition(trigger='shutdown', source='*', dest='EXIT')
        #self.machine.add_transition(trigger='shutdown', source='BID_PLACED', dest='BID_CANCELLING')
        #self.machine.on_enter_EXIT('cleanup')
    
    def set_risk(self, risk):
        self.risk = float(risk)
    
    def set_tick(self, event):
        self.bid = float(event.kwargs.get('bid'))
        self.ask = float(event.kwargs.get('ask'))
    
    def found_bid(self,event):
        self.bid_waiting_at = self.bid + self.bid_increments
        return True

    def retry_if_true(result):
        return result  

    #decorator to run job on thread (till it exits, so make sure it does)
    def asDaemon(worker_function):    
        def inner_function(self, *args):        
            print("create Thread()")
            thread = Thread(target=worker_function, args=(self,args))
            thread.daemon = True
            print("thread.starting()")
            thread.start()
        return inner_function        

    @asDaemon
    @retry(wait_fixed=1000, retry_on_result=retry_if_true)
    def retry_place_bid(self,event):
        print("try place bid")
        self.try_place_bid()
        return self.is_BID_SENDING()
            
    def bid_placed(self,event):
        self.bid_order = self.polo.buy(currencyPair = self.currency_pair, rate=self.bid_waiting_at, amount=self.amount)
        print ('placing bid @ ' + str(self.bid_waiting_at) + ' orderid: ' + self.bid_order['orderNumber'])
        return self.bid_order != None

        
        
    @asDaemon
    @retry(wait_fixed=1000, retry_on_result=retry_if_true)
    def retry_bid_confirm(self,event):
        print("try order")
        self.try_confirm_bid()
        return self.is_BID_WAIT_CONFIRM()
   
    def inBidOrder(self,event):
        print ('searching for order')
        orderbook = self.polo.returnOpenOrders(self.currency_pair)
        for order in orderbook:
            if order['orderNumber'] == self.bid_order['orderNumber']:
                print('order found')
                return True
        return False
    
    
    
    @asDaemon
    @retry(wait_fixed=1000, retry_on_result=retry_if_true)    
    def retry_bid_executed(self,event):
        print("checking if bid is executed")
        self.try_bid_executed()
        return self.is_BID_PLACED()

    def bid_executed(self,event):
        tradehistory = self.polo.returnTradeHistory(self.currency_pair)
        for trade in tradehistory:
            if trade['orderNumber'] == self.bid_order['orderNumber']:
                self.bid_position = float(trade['rate'])
                return True
        return False
   
    @asDaemon
    @retry(wait_fixed=1000, retry_on_result=retry_if_true)
    def retry_cancel_bid(self,event):
        print("cancelling bid")
        self.post_cancel_bid()
        return self.is_BID_CANCELLING()
    
    def bid_out_of_range(self,event):      
        delta = abs ( self.bid_waiting_at - self.bid )
        return ( delta > self.bid_delta ) 
    
    def cancel_bid(self,event):  
        if self.bid_order != None:
            print ('canceling bid @ ' + str(self.bid_position) + ' as market bid is ' + str(self.bid) + ' orderid was ' + self.bid_order['orderNumber'])
            result = self.polo.cancel(self.currency_pair,self.bid_order['orderNumber'])
            return result['success'] == 1
        return True

    def found_ask(self,event):
        self.ask_waiting_at = self.ask - self.bid_increments
        return True
    
    @asDaemon
    @retry(wait_fixed=1000, retry_on_result=retry_if_true)
    def retry_place_ask(self,event):
        print("try place ask")
        self.place_ask()
        return self.is_ASK_SENDING()
            
    def place_ask(self,event):
        self.ask_order = self.polo.buy(currencyPair = self.currency_pair, rate=self.ask_waiting_at, amount=self.amount)
        print ('placing ask @ ' + str(self.ask_waiting_at) + ' orderid: ' + self.ask_order['orderNumber'])
        return self.ask_order != None
    
    @asDaemon
    @retry(wait_fixed=1000, retry_on_result=retry_if_true)
    def retry_ask_placed(self,event):
        print("try order")
        self.ask_placed()
        return self.is_ASK_WAIT_CONFIRM()
   
    def isInBidOrderbook(self,event):
        orderbook = self.polo.returnOpenOrders(self.currency_pair)
        for order in orderbook:
            if order['orderNumber'] == self.ask_order['orderNumber']:
                return True
        return False
 
    @asDaemon
    @retry(wait_fixed=1000, retry_on_result=retry_if_true)    
    def retry_ask_executed(self,event):
        print("checking if bid is executed")
        self.ask_executed()
        return self.is_ASK_PLACED()

    def ask_executed(self,event):
        tradehistory = self.polo.returnTradeHistory(self.currency_pair)
        for trade in tradehistory:
            if trade['orderNumber'] == self.ask_order['orderNumber']:
                self.ask_position = trade['rate']
                return True
        return False 
    
    def set_ask_position(self,event):
        self.ask_position = self.ask_waiting_at
        print ('ask placed @ ' + str(self.ask_position))
    
    def bid_risk_exceeded(self,event):
        #return (self.risk > self.bid_position - self.bid)
        return False        
    

 

            

