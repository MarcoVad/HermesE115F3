"""
Control interface for FPGA peripherals using the USB serial port

The main reason to have this interface was to control DDS and QDUC peripherals which are connected to the FPGA by a SPI interface.
The control interface can be easily extended to control other systems or to set and query internal FPGA data.

The interface sends commands and receives the responses using sequences of binary data, called data frames.  
Data frame format:

    +--------+--------+---- --//-----+
    | opcode | lenght | payload      |
    | 1 byte | 1 byte | 0..255 bytes | 
    +--------+--------+----//--------+
    
When a command is sent, the response should have the same opcode. The lenght and payload must be either a copy of the send data (to acknowledge the 
command) or contain response data. 
When nothing is returned it could be that the frame sequencer got out of sync. That might happen when an invalid frame was sent or the FPGA was reset 
while a frame was ongoing. 
To resync, a number of 0x00 bytes are sent until a 0x00 is received. 
    
"""

import serial
import codecs
import re
import time
from math import log10

SPI_IORESET = '010101'
SPI_IOUPDATE = '010102'
hextobin = codecs.getdecoder('hex_codec')

DDS_CLK = 491.52E6
DDS_FMAX = 4294967296
DDS_PMAX = 16364
DDS_AMAX = 1023

# Frequency [Hz] to frequency tuning word 
DDS_FTOT = DDS_FMAX/DDS_CLK
# Frequency tuning word to frequency [Hz]
DDS_TTOF = DDS_CLK/DDS_FMAX

# Phase [degrees] to phase offset word
DDS_PTOT = DDS_PMAX/360.0
# Phase offset word to phase [degrees]
DDS_TTOP = 360.0/DDS_PMAX

# Amplitude [%] to Amplitude scale factor
DDS_ATOT = DDS_AMAX/100.003
# Amplitude scale factor to amplitude [%]
DDS_TTOA = 100.0/DDS_AMAX



class ControlInterface(object):
    
    def __init__(self, serialport):
        """
        """
        print ('ControlInterface using %s' %(serialport))
        self.ser = serial.Serial(serialport,  115200, timeout=0.1)
        
        self.dds_channels = 0  
        self.verbose = False  
           
    def bintohex(self, data):
        """
        Convert binary data to hex 
        """
        result = []
        for d in data:
            result.append('%02X'%d)
        
        return ' '.join(result)
               
     
    def send(self, data, check_length=False):
        """
        """
        
        if type(data) == bytes:
            data = data
        elif type(data) == str:
            data = re.sub(' ', '', data)
            data = hextobin(data)[0]
        else:
            print ('ControlInterface.send: invalid data (%s), type(%s)' %(data, type(data)))
           
        if self.ser.in_waiting > 0:
            flushread = self.ser.read(4096)
            if len(flushread)>0:
                print ('flushed %s' %(self.bintohex(flushread)))   
                if check_length:
                    raise Exception('unexpected data')
            
        self.ser.write(data)
        n = len(data)
        
        response = self.ser.read(4096)
        if self.verbose:
            print ('cmd %s --> %s' %(self.bintohex(data), self.bintohex(response)))
        if len(response) != n and check_length:
            raise Exception('data_lenght error')
            
        
        return response
       
      
    def SPI_reset(self):
        """
        """
        self.send(SPI_IORESET)
         
    def DDS_init(self):
        """
        Init DDS chip AD9959
        
        set 3-wire communication
        set PLL: PLL div 4, VCO gain high, charge pump 75uA (default)
        """
       
        result = True#
         
        response = self.send(f'030200F2 {SPI_IOUPDATE} 03028000')
        if len(response)>1 and response[-1] == 0xF2:
            print ('DDS init OK')
            # PLL
            self.send(f'030401900000 {SPI_IOUPDATE}')
        else:
            result = False
            print ('DDS init failed!')
            
        return result
        
    def DDS_set_frequency(self, channel, freq):
        """
        Updates the DDS FTW based on the SYSCLK of the DDS for the given channel(s)
        """
        # Set the channel bits
        chbits = (channel & 0x0F) << 4;
        ftw = round(freq * DDS_FTOT) & 0x7FFFFFFF
        result = ftw * DDS_TTOF
        self.send(f'030200%02X 030504%08X {SPI_IOUPDATE}' %(0x02 | chbits, ftw))
        
        return result 
       
    def DDS_set_phase(self, channel, phase):
        """
        Update the phase offset word of the given channel(s)
        @phase: phase value in degrees
        """
        while (phase<0): phase+=360.0
        while (phase>360.0): phase-=360.0

        # Set the channel bits 
        chbits = (channel & 0x0F) << 4
        pow = round(phase * DDS_PTOT) & 0xFFFF
        result = pow * DDS_TTOP
        self.send(f'030200%02X 030305%04X {SPI_IOUPDATE}' %(0x02 | chbits, pow))

        return result

    
    def DDS_set_amplitude(self, channel, amplitude):
        """
        Update the amplitude of the given channel(s)
        @amplitude: float between 0 and 100 
        """
        # Set the channel bits 
        chbits = (channel & 0x0F) << 4
        asf = round(amplitude * DDS_ATOT) & 0xFFFF
        result = asf * DDS_TTOA
        self.send(f'030200%02X 03040600%04X {SPI_IOUPDATE}' %(0x02 | chbits, asf | 0x1000))

        return result

        
    def QDUC_init(self): 
        """
        Init QDUC chip AD9957
        
        set 3-wire communication
        set PLL: PLL div 4, VCO gain high, charge pump 75uA (default)
        Clock input 32MHz
        """
       
        result = True
        response = self.send(f'02050000400002 02050100011840 0205023138C120 {SPI_IOUPDATE} 02058000000000')
        if len(response)>1 and self.bintohex(response[-4:]) == '00 40 00 02':
            print ('QDUC init OK')
        else:
            print ('QDUC init failed!')
            result = False
            
        return result
        

    def gain_test(self, sample, gain):
        s=''
        for i in sample.to_bytes(3, 'big', signed=True): s=s+'%02X' % i
        self.send('0A06 %s %06X' %(s, gain))
        a = self.send('0B03 000000')
        return int.from_bytes(a[2:5], 'big', signed=True)

        
        
        
if __name__ == "__main__":
    C = ControlInterface('/dev/ttyUSB0')
    #C.SPI_reset()
    #C.DDS_init()
    #C.verbose = True
   
   
    # gain test
    sample=1234567
    #for sample in (255310, -100000):
    while(1):    
        
        print("==== test sample %d =====" %(sample))
        print ("bit-wise sequence")
        for x in range(16):
            gain = 1<<x;
            g = gain/32768.0;
            expected = g * sample;
            result = C.gain_test(sample, gain);
            resgain = result/sample;
            try:
                print("gain(%d,%d)\tg %f (%f dB)\tresult %d\tresgain %f (%f dB)\terror %f" %(sample, gain, g, 20.0*log10(g), result, resgain, 20.0*log10(resgain), expected-result ));
            except:
                print("gain(%d,%d)\tg %f (%f dB)\tresult %d\tresgain %f  ??" %(sample, gain, g, 20.0*log10(g), result, resgain  ));
        print()
        print("linear sequence")
        for x in range(2000, 65536, 2000):
            gain = x;
            g = gain/32768.0;
            expected = g * sample;
            result = C.gain_test(sample, gain);
            resgain = result/sample;
            try:
                print("gain(%d,%d)\tg %f (%f dB)\tresult %d\tresgain %f (%f dB)\terror %f" %(sample, gain, g, 20.0*log10(g), result, resgain, 20.0*log10(resgain), expected-result ));
            except:
                print("gain(%d,%d)\tg %f (%f dB)\tresult %d\tresgain %f  ??" %(sample, gain, g, 20.0*log10(g), result, resgain  ));
                
        print ("====================")
    
    
    seq = 0 
    fails = 0
    fail_total = 0
    success = 0
    while 1:
        response1 = C.send('03028000 030481000000')
        #response1 = C.send('03028000')
        if len(response1) == 0:
            print ('No response')
            time.sleep(1)
            continue
            
        if C.bintohex(response1) == '03 02 FF F2 03 04 00 90 00 00':
        #if C.bintohex(response1) == '03 02 FF F2':
            success += 1
            time.sleep(0.2)
            if seq == 0:
                C.DDS_set_frequency(15, 145.0E6)
                seq += 1
            else:
                C.DDS_set_frequency(15, 145.000110E6)
                seq = 0
                
        else:
            print (C.bintohex(response1))
            fail_total +=1

            # init the device
            C.SPI_reset()
                
            #C.send('030200F2')          # write CSR register:  3-wire mode and 'LSB first'
            #C.send('010102')            # IO-Update pulse
            #C.send('030401900000')      # write FR1 register: PLL div = 4
            #C.send('010102')            # IO-Update pulse
            C.send(f'030200F2 {SPI_IOUPDATE} 030401900000 {SPI_IOUPDATE}')
        
        print ('success/fail %s/%s %0.2f%%' %(success, fail_total, 100*(fail_total/(success+fail_total))) )
         
            
    
    
    while 0:
        freq = C.DDS_set_frequency(0x0F, 1E6)
        print ('Frequency set to %f MHz' %(freq/1E6))
        time.sleep(1)
        freq = C.DDS_set_frequency(0x0F, 2E6)
        print ('Frequency set to %f MHz' %(freq/1E6))
        time.sleep(1)
    
    