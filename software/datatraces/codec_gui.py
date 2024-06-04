"""
PE1NWK 
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

        self.codecResBtn = QtWidgets.QPushButton(text = 'Codec reset')
        setCustomSize(self.codecResBtn, 100, 40)
        self.codecResBtn.clicked.connect(self.codecResBtnAction)
        layout.addWidget(self.codecResBtn, *(0,0))

        self.traceBtnRes = QtWidgets.QPushButton(text = 'trace reset')
        setCustomSize(self.traceBtnRes, 100, 40)
        self.traceBtnRes.clicked.connect(self.traceBtnResAction)
        layout.addWidget(self.traceBtnRes, *(1,0))

        self.traceBtnUpd = QtWidgets.QPushButton(text = 'trace update')
        setCustomSize(self.traceBtnUpd, 100, 40)
        self.traceBtnUpd.clicked.connect(self.traceBtnUpdAction)
        layout.addWidget(self.traceBtnUpd, *(2,0))

        ########################
        # audio codec settings #
        ########################
        #/
         
        label_gain = QtWidgets.QLabel('line gain')
        layout.addWidget(label_gain, *(0,1))
        
        self.gainSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.gainSlider.setMinimum(0)
        self.gainSlider.setMaximum(31)
        self.gainSlider.setSingleStep(1)
        self.gainSlider.valueChanged.connect(self.gainSliderAction)
        layout.addWidget(self.gainSlider, *(0,2))
        
        self.checkbox_linein = QtWidgets.QCheckBox('line in')
        self.checkbox_linein.stateChanged.connect(self.lineinAction)
        layout.addWidget(self.checkbox_linein, *(1,1))

        self.checkbox_micboost = QtWidgets.QCheckBox('mic boost')
        self.checkbox_micboost.stateChanged.connect(self.micboostAction)
        layout.addWidget(self.checkbox_micboost, *(1,2))
        #\
        #######################

        # Statusbar
        self.setStatusBar(QtWidgets.QStatusBar(self))
        self.show()
        self.config = 0
       

    def codecResBtnAction(self):
        print("Codec reset")
        response = self.fpga_control.send('01 01 08')
        if self.fpga_control.bintohex(response) == '01 01 08':
            self.codecResBtn.setStyleSheet("background-color: green")
        else:
            self.codecResBtn.setStyleSheet("background-color: red")
        self.update()

    def traceBtnResAction(self):
        self.traceBtnAction('Reset')
    
    def traceBtnUpdAction(self):
        self.traceBtnAction('Update')
    
    def traceBtnAction(self, trigger):
        #self.fpga_control.verbose = False
        trace_id = -1
        
        if trigger == 'Reset':
            print ('Trace data trigger on codec reset')
            resp = self.fpga_control.send('0C 01 01 01 01 08', check_length=False)
            
        if trigger == 'Update':
            print ('Trace data trigger on codec update')
            self.fpga_control.send('0D 01 %02X' %(self.config ^ 1))
            resp = self.fpga_control.send('0C 01 01 0D 01 %02X' %(self.config), check_length=False)

        
        if resp[2] & 0xF0 == 0x20:
            trace_id = resp[2] & 0x0F
        print ("Trace ID", trace_id)
        
        if trace_id < 1:
            print ("Trace ID %d not valid. Maybe not data tracing is not configured in FPGA? (Recompile needed)" %(trace_id))
            return 

        if trace_id not in (4, 5):
            print ("Trace ID %d not supported" %(trace_id))
            return

        if len(resp) > 6:
            bdata = resp[6:]
        else:
            bdata = b''
            
        data = []
        datalen = 0
        
        for t in range(20):
            time.sleep(0.1)
            bdata += self.fpga_control.ser.read(4096)
            if len(bdata) >= 2048:
                break
        
        time.sleep(0.5)
        bdata += self.fpga_control.ser.read(4096)
            
        bdata = bdata[1:-3] # temp fix for shifted bytes    
            
        ln = len(bdata)
        for i in range (0,ln,4):
            try:
                worddata = (bdata[i+3] << 24) + (bdata[i+2] << 16) + (bdata[i+1] << 8) + bdata[i] 
                if (bdata[i+1] & 0xE0) == 0x00:
                    data.append(worddata)
                else:
                    print ('data error at %d, data %08X'%(i, worddata))
            
            except: break
        
        print ('bytes', len(bdata))
        hexdump.hexdump(bdata)

        print ('data', len(data))
       
        if trace_id == 4: 
            self.write_vcd_file_CODEC_CFG(data)
        if trace_id == 5: 
            self.write_vcd_file_CODEC_MIC(data)
        self.fpga_control.verbose = True
        
    
    def write_vcd_file_CODEC_CFG(self, data):
        """
        Write the traces in data to a vcd file, to be viewed by GTKWave
          {running, update_required, reset_n, wr_request, busy, init_required, sda, scl,
          word_no, 2'b0, state,
          3'b0, wr_data};    
        """
        filename = 'codec_cfg_gui.vcd' 
        ts = 0
        
        with VCDWriter(open(filename, 'w'), timescale='1 ns', date='today') as writer:
            running_var =  writer.register_var('CODEC_CFG', 'running', 'integer', size=1)    
            updreq_var =   writer.register_var('CODEC_CFG', 'update_required', 'integer', size=1)    
            resetn_var =   writer.register_var('CODEC_CFG', 'reset_n', 'integer', size=1)    
            wr_req_var =   writer.register_var('CODEC_CFG', 'wr_request', 'integer', size=1)    
            busy_var =     writer.register_var('CODEC_CFG', 'busy', 'integer', size=1)    
            init_req_var = writer.register_var('CODEC_CFG', 'init_required', 'integer', size=1)    
            SDA_var =      writer.register_var('CODEC_CFG', 'SDA', 'integer', size=1)    
            SCL_var =      writer.register_var('CODEC_CFG', 'SCL', 'integer', size=1)    
            word_no_var =  writer.register_var('CODEC_CFG', 'word_no', 'integer', size=4)    
            state_var =    writer.register_var('CODEC_CFG', 'state', 'integer', size=4)    
            datawr_var =   writer.register_var('CODEC_CFG', 'datawr', 'integer', size=16)     
            bclk_var =     writer.register_var('CODEC_CFG', 'bclk', 'integer', size=16)     
                
            for t, d in enumerate(data):
                ts += 1302
                running = (d>>31) & 0x01
                updreq = (d>>30) & 0x01
                resetn = (d>>29) & 0x01
                wr_req = (d>>28) & 0x01
                busy = (d>>27) & 0x01
                init_req = (d>>26) & 0x01
                SDA = (d>>25) & 0x01
                SCL = (d>>24) & 0x01
                word_no = (d>>20) & 0x0F
                state = (d>>16) & 0x0F
                datawr = d & 0xFFFF
                bclk = (t%4)
                
                #print (ts,resetn,enable,busy,prevbusy,SDA,SCL,initcnt,state,datawr)
                
                writer.change(running_var, ts, running)
                writer.change(updreq_var, ts, updreq)
                writer.change(resetn_var, ts, resetn)
                writer.change(wr_req_var, ts, wr_req)
                writer.change(busy_var, ts, busy)
                writer.change(init_req_var, ts, init_req)
                writer.change(SDA_var, ts, SDA)
                writer.change(SCL_var, ts, SCL)
                writer.change(word_no_var, ts, word_no)
                writer.change(state_var, ts, state)
                writer.change(datawr_var, ts, datawr)
                writer.change(bclk_var, ts, bclk)
                
        print ('timespan 0..%f us' %(ts/1000))
        print ('wrote data to', filename) 

    
    def write_vcd_file_CODEC_MIC(self, data):
        """
        Write the traces in data to a vcd file, to be viewed by GTKWave
        """
        filename = 'codec_mic_gui.vcd' 
        ts = 0
        
        with VCDWriter(open(filename, 'w'), timescale='1 ns', date='today') as writer:
            micdata_var =  writer.register_var('CODEC_MIC', 'micdata', 'integer', size=16)    
            state_var  =   writer.register_var('CODEC_MIC', 'state', 'integer', size=5)    
            CBCLK_var =    writer.register_var('CODEC_MIC', 'CBCLK', 'integer', size=1)    
            CLRCLK_var =   writer.register_var('CODEC_MIC', 'CLRCLK', 'integer', size=1)    
            CDOUT_var =    writer.register_var('CODEC_MIC', 'CDOUT', 'integer', size=1)    
            ready_var =    writer.register_var('CODEC_MIC', 'ready', 'integer', size=1)    
                
            for t, d in enumerate(data):
                ts += 81
                micdata = (d>>16) & 0xFFFF
                state = (d>>8) & 0x1F
                CBCLK = (d>>7) & 0x01
                CLRCLK = (d>>6) & 0x01
                CDOUT = (d>>5) & 0x01
                ready = (d>>4) & 0x01
                
                #print (ts,resetn,enable,busy,prevbusy,SDA,SCL,initcnt,state,datawr)
                
                writer.change(micdata_var, ts, micdata)
                writer.change(state_var, ts, state)
                writer.change(CBCLK_var, ts, CBCLK)
                writer.change(CLRCLK_var, ts, CLRCLK)
                writer.change(CDOUT_var, ts, CDOUT)
                writer.change(ready_var, ts, ready)
                
        print ('timespan 0..%f us' %(ts/1000))
        print ('wrote data to', filename) 

            
    def gainSliderAction(self, value):
        self.codec_cfg_changed()

    def lineinAction(self, value):
        self.codec_cfg_changed()

    def micboostAction(self, value):
        self.codec_cfg_changed()

    def codec_cfg_changed(self):
        self.config = self.gainSlider.value()
        if self.config >= 31:
            self.config = 31
        if self.checkbox_linein.isChecked():
            self.config |= 0x20 
        
        if self.checkbox_micboost.isChecked():
            self.config |= 0x40 
        
        self.fpga_control.send('0D 01 %02X' %(self.config))


app = QtWidgets.QApplication(sys.argv)
w = MainWindow()
app.exec_()
