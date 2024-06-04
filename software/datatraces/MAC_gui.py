"""
graphical user interface for plotting signal levels and antenna positions

interesting links:
http://www.seed-solutions.com/gregordy/Amateur%20Radio/Experimentation/SMeterBlues.htm
https://www.learnpyqt.com/courses/graphics-plotting/plotting-matplotlib/
"""

import sys
import time
import datetime
import random
import argparse
from hexdump import hexdump
import binascii

from PyQt5 import QtCore, QtWidgets, QtGui

import ControlInterface
from vcd import VCDWriter

def setCustomSize(x, width, height):
    sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
    sizePolicy.setHorizontalStretch(0)
    sizePolicy.setVerticalStretch(0)
    sizePolicy.setHeightForWidth(x.sizePolicy().hasHeightForWidth())
    x.setSizePolicy(sizePolicy)
    x.setMinimumSize(QtCore.QSize(width, height))
    x.setMaximumSize(QtCore.QSize(width, height))
    
class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        parser = argparse.ArgumentParser()
        parser.add_argument('--serialport', default='/dev/ttyUSB0')
        args = parser.parse_args()
        
        self.fpga_control = ControlInterface.ControlInterface(args.serialport)
        self.fpga_control.verbose = True

        # Create FRAME_A
        frame = QtWidgets.QFrame(self)
        frame.setStyleSheet("QWidget { background-color: %s }" % QtGui.QColor(210,235,210,255).name())
        vlayout = QtWidgets.QVBoxLayout()
        frame.setLayout(vlayout)
        self.setCentralWidget(frame)

        layout = QtWidgets.QGridLayout()
        vlayout.addLayout(layout)

        hlayout = QtWidgets.QHBoxLayout()
        
        
        vlayout.addLayout(hlayout)

        self.phyResBtn = QtWidgets.QPushButton(text = 'PHY HW reset')
        setCustomSize(self.phyResBtn, 100, 40)
        self.phyResBtn.clicked.connect(self.phyResBtnAction)
        layout.addWidget(self.phyResBtn, *(0,0))

        self.phySWResBtn = QtWidgets.QPushButton(text = 'PHY SW reset')
        setCustomSize(self.phySWResBtn, 100, 40)
        self.phySWResBtn.clicked.connect(self.phySWResBtnAction)
        layout.addWidget(self.phySWResBtn, *(1,0))

        self.traceBtn = QtWidgets.QPushButton(text = 'trace data')
        setCustomSize(self.traceBtn, 100, 40)
        self.traceBtn.clicked.connect(self.traceBtnAction)
        layout.addWidget(self.traceBtn, *(3,0))


        # Statusbar
        self.setStatusBar(QtWidgets.QStatusBar(self))
        
        self.show()
       
            

    def phyResBtnAction(self):
        print("PHY HW reset")
        response = self.fpga_control.send('01 01 04')
        if self.fpga_control.bintohex(response) == '01 01 04':
            self.phyResBtn.setStyleSheet("background-color: green")
        else:
            self.phyResBtn.setStyleSheet("background-color: red")
        self.update()


    def phySWResBtnAction(self):
        print("PHY SW reset")
        self.phySWResBtn.setStyleSheet("background-color: green")
        
        label = self.RegLabels[0]
        try:
            response = self.fpga_control.send('0A 03 00 00 00')
            data = self.fpga_control.bintohex(response).split(' ')
            if data[0:3] != ['0A','03','00']:
                 raise SystemError("Communication failure")
            
            # set bit 15 
            self.fpga_control.send('0B 03 00 %02X %02X' %(response[3] | 0x80, response[4] ))
            response = self.fpga_control.send('0A 03 00 00 00')
            data2 = self.fpga_control.bintohex(response).split(' ')
            if data2[0:3] != ['0A','03','00']:
                label.setText('Reg 0\n????')
                raise SystemError("Communication failure")
                
            label.setText('Reg 0\n%s%s' %(data2[3], data2[4]))
            
        except Exception as e:
            print (str(e))
            self.phySWResBtn.setStyleSheet("background-color: red")
            
        self.update()

            
    def traceBtnAction(self):
        self.fpga_control.verbose = False
        trace_id = -1
        resp = self.fpga_control.send('0C 01 01')
        if resp[2] & 0xF0 == 0x20:
            trace_id = resp[2] & 0x0F
        print ("Trace ID", trace_id)
        
        if trace_id < 1:
            print ("Trace ID %d not valid. Maybe not data tracing is not configured in FPGA? (Recompile needed)" %(trace_id))
            return 

        if trace_id != 3:
            print ("Trace ID %d not supported" %(trace_id))
            return
         
        data = []
        datalen = 0
        data_counter = 0
        bdata = b''
        
        for t in range(50):
            time.sleep(0.1)
            bdata += self.fpga_control.ser.read(4096)
            if len(bdata) >= 2048:
                break

        bdata = bdata[1:-3] # temp fix for shifted bytes    
        
        print ('bytes', len(bdata))
        #hexdump.hexdump(bdata)
       
        for i in range (0,len(bdata),4):
            try:
                worddata = (bdata[i+3] << 24) + (bdata[i+2] << 16) + (bdata[i+1] << 8) + bdata[i] 
                if bdata[i+3] == 0x60:
                    data.append(worddata)
                else:
                    print ('data error at %d, data %08X'%(i, worddata))
            
            except: break
       

        print ('data', len(data))
        
        self.write_vcd_file_MAC(data)
        self.fpga_control.verbose = True
        
    
    def write_vcd_file_MAC(self, data):
        """
        Write the traces in data to a vcd file, to be viewed by GTKWave
        """
        recovered = b''
        alldata = b''
        filename = 'MAC_gui.vcd' 
        
        with VCDWriter(open(filename, 'w'), timescale='1 ns', date='today') as writer:
            rxdata_var = writer.register_var('MAC', 'rxdata', 'integer', size=8)    
            state_var = writer.register_var('MAC', 'state', 'integer', size=5)    
            byteno_var = writer.register_var('MAC', 'byteno', 'integer', size=3)    
            mac_rx_enable_var = writer.register_var('MAC', 'mac_rx_enable', 'integer', size=1)    
            mac_rx_active_var = writer.register_var('MAC', 'mac_rx_active', 'integer', size=1)    
            broadcast_var = writer.register_var('MAC', 'broadcast', 'integer', size=1)    
            rx_is_arp_var = writer.register_var('MAC', 'rx_is_arp', 'integer', size=1)    
            rx_is_icmp_var = writer.register_var('MAC', 'rx_is_icmp', 'integer', size=1)    
            ip_rx_active_var = writer.register_var('MAC', 'ip_rx_active', 'integer', size=1)    
            udp_rx_active_var = writer.register_var('MAC', 'udp_rx_active', 'integer', size=1)    
            dhcp_rx_active_var = writer.register_var('MAC', 'dhcp_rx_active', 'integer', size=1)    
                
            for t, d in enumerate(data):
                ts = t * 8
                rxdata = d & 0xFF
                state = (d>>8) & 0x1F
                byteno = (d>>13) & 0x07 
                dhcp_rx_active = (d>>23) & 0x01
                udp_rx_active = (d>>22) & 0x01
                ip_rx_active = (d>>21) & 0x01
                rx_is_icmp = (d>>20) & 0x01
                rx_is_arp = (d>>19) & 0x01
                broadcast = (d>>18) & 0x01
                mac_rx_active = (d>>17) & 0x01
                mac_rx_enable = (d>>16) & 0x01
               
                bdata = rxdata.to_bytes(1, byteorder='big')
                if mac_rx_enable: 
                    recovered += bdata
                alldata += bdata
                
                
                writer.change(rxdata_var, ts, rxdata)
                writer.change(state_var, ts, state)
                writer.change(byteno_var, ts, byteno)
                writer.change(dhcp_rx_active_var, ts, dhcp_rx_active)
                writer.change(udp_rx_active_var, ts, udp_rx_active)
                writer.change(ip_rx_active_var, ts, ip_rx_active)
                writer.change(rx_is_icmp_var, ts, rx_is_icmp)
                writer.change(rx_is_arp_var, ts, rx_is_arp)
                writer.change(broadcast_var, ts, broadcast)
                writer.change(mac_rx_active_var, ts, mac_rx_active)
                writer.change(mac_rx_enable_var, ts, mac_rx_enable)
                
        print ('timespan 0..%f us' %(ts/1000))
        print ('wrote data to', filename) 

        if len(recovered) > 0:
            print ('\nrecovered data:')
            hexdump.hexdump(recovered)
        else:
            print ('\ninvalid data:')
            hexdump.hexdump(alldata)
            



app = QtWidgets.QApplication(sys.argv)
w = MainWindow()
app.exec_()
