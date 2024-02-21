import utime

class StopWatch():
    def __init__(self):
        self.begT = utime.ticks_ms()
        
    def reset(self):
        self.begT = utime.ticks_ms()
    
    def duration (self, ms, rst:bool=False):
        cc = utime.ticks_ms() - self.begT
        if cc >= ms:
            if rst:
                self.reset()

            return True
        else:
            return False      
