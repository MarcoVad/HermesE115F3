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
        
        label_reg = QtWidgets.QLabel('Reg')
        setCustomSize(label_reg, 50, 40)
        self.regEdit = QtWidgets.QLineEdit(text = '15')
        self.regEdit.setMaximumWidth(50)
        label_value = QtWidgets.QLabel('Value')
        setCustomSize(label_value, 50, 40)
        self.valEdit = QtWidgets.QLineEdit(text = '1234')
        self.valEdit.setMaximumWidth(50)
        self.WriteRegBtn = QtWidgets.QPushButton(text = 'Write reg')
        setCustomSize(self.WriteRegBtn, 100, 40)
        self.WriteRegBtn.clicked.connect(self.WriteRegBtnAction)
        
        hlayout.addWidget(label_reg)
        hlayout.addWidget(self.regEdit)
        hlayout.addWidget(label_value)
        hlayout.addWidget(self.valEdit)
        hlayout.addWidget(self.WriteRegBtn)
        hlayout.addStretch()
        
        vlayout.addLayout(hlayout)

        self.phyResBtn = QtWidgets.QPushButton(text = 'PHY HW reset')
        setCustomSize(self.phyResBtn, 100, 40)
        self.phyResBtn.clicked.connect(self.phyResBtnAction)
        layout.addWidget(self.phyResBtn, *(0,0))

        self.phySWResBtn = QtWidgets.QPushButton(text = 'PHY SW reset')
        setCustomSize(self.phySWResBtn, 100, 40)
        self.phySWResBtn.clicked.connect(self.phySWResBtnAction)
        layout.addWidget(self.phySWResBtn, *(1,0))

        self.readregsBtn = QtWidgets.QPushButton(text = 'read registers')
        setCustomSize(self.readregsBtn, 100, 40)
        self.readregsBtn.clicked.connect(self.readregsBtnAction)
        layout.addWidget(self.readregsBtn, *(2,0))

        self.traceBtn = QtWidgets.QPushButton(text = 'trace data')
        setCustomSize(self.traceBtn, 100, 40)
        self.traceBtn.clicked.connect(self.traceBtnAction)
        layout.addWidget(self.traceBtn, *(3,0))

        self.RegLabels=[]
        for i in range(32):
            label = QtWidgets.QLabel()
            label.setText('Reg %d' %(i))
            layout.addWidget(label, *(i // 8,4 + i%8))
            self.RegLabels.append(label)

        # Statusbar
        self.setStatusBar(QtWidgets.QStatusBar(self))
        
        self.show()
       
    def WriteRegBtnAction(self):
        """
        Write a value to a PHY register
        """
        self.WriteRegBtn.setStyleSheet("background-color: green")
        try:
            reg = int(self.regEdit.text())
            if reg<0 or reg>31:
                raise ValueError("Reg incorrect")
            value, ln = ControlInterface.hextobin(self.valEdit.text())
            if ln != 4:
                raise ValueError("value should be 4 hex characters")
            hexvalue = self.fpga_control.bintohex(value)
            
            print ("Write Reg %d: %s" %(reg, hexvalue ))
            label = self.RegLabels[reg]
            self.fpga_control.send('0B 03 %02X %02X %02X' %(reg, value[0], value[1] ))
            response = self.fpga_control.send('0A 03 %02X 00 00' %(reg))
            data2 = self.fpga_control.bintohex(response).split(' ')
            if data2[0:3] == ['0A','03','%02X' %(reg)]:
                label.setText('Reg %d\n%s%s' %(reg, data2[3], data2[4]))
            else:
                label.setText('Reg %d\n????' %(reg))
                raise SystemError("Communication failure")
            
        except Exception as e:
            print (str(e))
            self.WriteRegBtn.setStyleSheet("background-color: red")
        
            

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

            
    def readregsBtnAction(self):
        while 1:
            print("read all registers")
            for r in range(32):
                label = self.RegLabels[r]
                response = self.fpga_control.send('0A 03 %02X 00 00' %(r))
                if len(response) != 5:
                    raise Exception('data size error')
                data = self.fpga_control.bintohex(response).split(' ')
                if data[0:3] == ['0A','03', '%02X' %(r)]:
                    label.setText('Reg %s\n%s%s' %(r, data[3], data[4]))
                else:
                    label.setText('Reg %s\n????' %(r))
                self.update()
            break

    def traceBtnAction(self):
        #self.fpga_control.verbose = False
        trace_id = -1
        resp = self.fpga_control.send('0C 01 01')
        if resp[2] & 0xF0 == 0x20:
            trace_id = resp[2] & 0x0F
        print ("Trace ID", trace_id)
       
        if trace_id < 1:
            print ("Trace ID %d not valid. Maybe not data tracing is not configured in FPGA? (Recompile needed)" %(trace_id))
            return 

        if len(resp) > 3:
            bdata = resp[3:]
        else:
            bdata = b''
       
        data = []
        datalen = 0
        
        for t in range(50):
            time.sleep(0.1)
            bdata += self.fpga_control.ser.read(4096)
            if len(bdata) >= 2048:
                break
        
        time.sleep(0.5)
        bdata += self.fpga_control.ser.read(4096)

        if trace_id > 2:
            print ("Trace ID %d not supported" %(trace_id))
            return

        
        bdata = bdata[1:-3] # temp fix for shifted bytes    
        
        print ('bytes', len(bdata))
        hexdump.hexdump(bdata)
       
        for i in range (0,len(bdata),4):
            try:
                #  {data_wire[3:0], 2'b01, debh[9:0], data_wire[7:4], 2'b10, debl[9:0]};
                worddata = (bdata[i+3] << 24) + (bdata[i+2] << 16) + (bdata[i+1] << 8) + bdata[i] 
                if (bdata[i+3] &0x0C) == 0x04 and (bdata[i+1] & 0x0C) == 0x08:
                    data.append(worddata & 0xFFFF)
                    data.append((worddata >> 16) & 0xFFFF)
                else:
                    print ('data error at %d, data %08X'%(i, worddata))
            
            except: 
                break

        print ('data', len(data))
        
        self.new_trace_data(data, trace_id)

        self.fpga_control.verbose = True
        
        
    def new_trace_data(self, data, trace_id):
        """
        trace_id 1:  highspeed format (at 375 MHz):
        for this to work, define DEBUG_PHY_HS in Hermes.qsf 
            {data_wire[3:0], sample clock 01, PHY_RX_CLOCK, PHY_DV, PHY_RX} 
            {data_wire[7:4], sample clock 10, PHY_RX_CLOCK, PHY_DV, PHY_RX} 
           sample clock is 01 at a 0 -> 1 transition
           sample clock is 10 at a 1 -> 0 transition
           
        trace_id 2: normal speed format (at PHY_RX_CLOCK speed):
        for this to work, define DEBUG_PHY in Hermes.qsf 
            {PHY_RX[3:0], 2'b01, payload_coming, active, data} 
            {PHY_RX[3:0], 2'b10, payload_coming, active, data}
        """
        
        if trace_id == 1:
            self.write_vcd_file_HS(data)

        elif trace_id == 2:
            self.write_vcd_file(data)
            
    
    def write_vcd_file(self, data):
        """
        Write the traces in data to a vcd file, to be viewed by GTKWave
        """
        recovered = b''
        phyrx_l = 0
        phyrx_h = 0
        phyrx_c = 0
        ts = 0
        filename = 'phyconfig_gui.vcd' 
        
        with VCDWriter(open(filename, 'w'), timescale='1 ns', date='today') as writer:
            rxdata_var = writer.register_var('PHY_RX', 'data', 'integer', size=8)    
            active_var = writer.register_var('PHY_RX', 'active', 'integer', size=1)    
            preamble_var = writer.register_var('PHY_RX', 'preamble', 'integer', size=1)    
            rxclk_var = writer.register_var('PHY_RX', 'RXCLK', 'integer', size=1)    
            phyrx_n_var = writer.register_var('PHY_RX', 'PHYRX', 'integer', size=4)    
            phyrx_c_var = writer.register_var('PHY_RX', 'PHYRX_combined', 'integer', size=8)    
                
            for t, d in enumerate(data):
                ts += 8
                rxdata = d & 0xFF
                active = (d>>8) & 0x01
                preamble = (d>>9) & 0x01
                rxclk = (d>>10) & 0x01 
                phyrx_n = (d>>12) & 0x0F
                
                if rxclk:
                    phyrx_l = phyrx_n
                else:
                    phyrx_h = phyrx_n
                    phyrx_c = (phyrx_h << 4) + phyrx_l
                    if active>0: 
                        recovered += phyrx_c.to_bytes(1,'big')
                
                writer.change(rxdata_var, ts, rxdata)
                writer.change(active_var, ts, active)
                writer.change(preamble_var, ts, preamble)
                writer.change(rxclk_var, ts, rxclk)
                writer.change(phyrx_n_var, ts, phyrx_n)
                writer.change(phyrx_c_var, ts, phyrx_c)
                
        print ('timespan 0..%f us' %(ts/1000))
        print ('wrote data to', filename) 

        print ('\nrecovered data:')
        hexdump.hexdump(recovered)
        print()

    def write_vcd_file_HS(self, data):
        """
        Write the traces in data to a vcd file, to be viewed by GTKWave
        """
        
        recovered = b''
        datawire_l = 0
        datawire_h = 0
        datawire = 0
        prev_rxclk = 0
        filename = 'phyconfig_gui_HS.vcd' 
        ts = 0
        
        with VCDWriter(open(filename, 'w'), timescale='1 ps', date='today') as writer:
            phyrx_var = writer.register_var('PHY_RX', 'PHY_RX', 'integer', size=8)    
            dv_var = writer.register_var('PHY_RX', 'DV', 'integer', size=1)    
            rxclk_var = writer.register_var('PHY_RX', 'RXCLK', 'integer', size=1)    
            clk_var = writer.register_var('PHY_RX', 'sample_clk', 'integer', size=1)    
            datawire_l_var = writer.register_var('PHY_RX', 'data_wireL', 'integer', size=4)    
            datawire_h_var = writer.register_var('PHY_RX', 'data_wireH', 'integer', size=4)    
            datawire_var = writer.register_var('PHY_RX', 'data_wire', 'integer', size=8)    
            for t, d in enumerate(data):
                ts += 1333
                phyrx = d & 0xFF
                dv = (d>>8) & 0x01
                rxclk = (d>>9) & 0x01 
                clk = (d>>10) & 0x01
                datawire_n = (d>>12) & 0x0F
                
                if clk:
                    datawire_l = datawire_n
                else:
                    datawire_h = datawire_n
                 
                if prev_rxclk != rxclk and rxclk==1:
                    datawire = (datawire_h << 4) + datawire_l
                    if dv>0: 
                        recovered += datawire.to_bytes(1, 'big')
                prev_rxclk = rxclk
                
                writer.change(phyrx_var, ts, phyrx)
                writer.change(dv_var, ts, dv)
                writer.change(rxclk_var, ts, rxclk)
                writer.change(clk_var, ts, clk)
                writer.change(datawire_l_var, ts, datawire_l)
                writer.change(datawire_h_var, ts, datawire_h)
                writer.change(datawire_var, ts, datawire)
                
        print ('timespan 0..%f us' %(ts/1000))
        print ('wrote data to', filename) 

        print ('\nrecovered data:')
        hexdump.hexdump(recovered)
        print()
    
            



app = QtWidgets.QApplication(sys.argv)
w = MainWindow()
app.exec_()
