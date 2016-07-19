from transitions import Machine

class Matter(object):
    def __init__(self): 
        self.machine = Machine(self, ['solid', 'liquid'], send_event=True, initial='solid')
        self.machine.add_transition('melt', 'solid', 'liquid', prepare='set_environment', conditions='is_greater_than_melt')
        self.temp = 0
        self.pressure = 101.325
    def set_environment(self, event):
        self.temp = event.kwargs.get('temp')
        self.pressure = event.kwargs.get('pressure')
    def print_temperature(self): print("Current temperature is %d degrees celsius." % self.temp)
    def print_pressure(self): print("Current pressure is %.2f kPa." % self.pressure)
    def is_greater_than_melt(self,event): 
        print (self.temp)
        return (self.temp > 100)
   
lump = Matter()
