//
//  HPSDR - High Performance Software Defined Radio
//
//  Metis code. 
//
//  This program is free software; you can redistribute it and/or modify
//  it under the terms of the GNU General Public License as published by
//  the Free Software Foundation; either version 2 of the License, or
//  (at your option) any later version.
//
//  This program is distributed in the hope that it will be useful,
//  but WITHOUT ANY WARRANTY; without even the implied warranty of
//  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//  GNU General Public License for more details.
//
//  You should have received a copy of the GNU General Public License
//  along with this program; if not, write to the Free Software
//  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA


//  Metis code copyright 2010, 2011, 2012, 2013 Alex Shovkoplyas, VE3NEA.

//  25 Sept 2014 - Modified initial register values to correct for 0.12nS rather than 0.2nS steps.
//                 Also added write to register 106h to turn off Tx Data Pad Skews.  Both these
//						 changes are due to errors in the original data sheet which was corrected Feb 2014.


//-----------------------------------------------------------------------------
// initialize the PHY device on startup and when allow_1Gbit changes
// by writing config data to its MDIO registers; 
// continuously read PHY status from the MDIO registers
//-----------------------------------------------------------------------------

module phy_cfg(
  //input
  input clock,        //2.5 MHZ
  input reset_n,
  input init_request,
  input allow_1Gbit,            
  input enable_clock_skew, 
  input mdio_rd_request,
  input mdio_wr_request,
  input [7:0] mdio_register,
  input [15:0] mdio_wr_data,
  
  
  //output
  output reg [1:0] speed,
  output reg duplex,
  output reg [15:0] mdio_rd_data,
  output reg mdio_rw_busy,
  output reg init_busy,
  
  //hardware pins
  inout mdio_pin,
  output mdc_pin  
);


//-----------------------------------------------------------------------------
//                           initialization data
//-----------------------------------------------------------------------------
localparam NUMREG = 4'd4; // number of registers to set/get during init
   
//mdio register values
logic [15:0] values [NUMREG-1:0];

//mdio register addresses 
logic [4:0] addresses [NUMREG-1:0];

reg [3:0] word_no; 
localparam MDIOREG = 4'd1; // index for addresses/values to temporarily store mdio request 

//-----------------------------------------------------------------------------
//                            state machine
//-----------------------------------------------------------------------------

//phy initialization required 
//if allow_1Gbit input has changed or init_request input was raised
reg last_allow_1Gbit, init_required;

wire ready;
wire [15:0] rd_data;
reg rd_request, wr_request;
reg r_mdio_rdreq;
reg r_mdio_wrreq;


//state machine  
localparam 
   READING = 2'd0, 
   WRITING = 2'd1,
   MDIORDREQ = 2'd2,
   MDIOWRREQ = 2'd3;
   
reg [1:0] state = READING;  

always @(posedge clock or negedge reset_n)  
begin
  if (!reset_n)
  begin
     speed <= 2'h0;
     duplex <= 1'd0;
     mdio_rw_busy <= 1'b0;
     r_mdio_rdreq <= 1'b0;
     r_mdio_wrreq <= 1'b0;
     init_busy <= 1'b0;
  end else
  begin
  if (init_request || (allow_1Gbit != last_allow_1Gbit))  begin
    init_required <= 1'b1;
    init_busy <= 1'b1;
    
    // For Marvel 88E1111 PHY:
    values[3] = 16'h808B;                   // RGMII mode
    values[2] = 16'h0CE0;                   // RXCLK skew
    values[1] = 16'h9140;                   // Reset the PHY to apply the autonegotiation values
    values[0] = 16'h0000;                   // Link status register (for reading)
    addresses[3] = 27;
    addresses[2] = 20;
    addresses[1] = 0;
    addresses[0] = 17;
  end
 
  // capture and latch a mdio read request because the read pulse may be too short to be seen by the state machine
  // Also flag the mdio_rw_busy for the requester
  if (mdio_rd_request) begin
     r_mdio_rdreq <= 1'b1;
     mdio_rw_busy <= 1'b1;
  end

  if (mdio_wr_request) begin
     r_mdio_wrreq <= 1'b1;
     mdio_rw_busy <= 1'b1;
  end
  
  // The state machine is only triggered when a mdio request is ready. A frame takes 64 clk cycles @2.5 MHz -> 25.6 us per frame
  if (ready)
    case (state)
      READING:
        begin
        if (r_mdio_rdreq)
           begin
              word_no <= MDIOREG;
              addresses[MDIOREG] <= mdio_register[4:0];
              state <= MDIORDREQ;
              rd_request <= 1'b1;
              r_mdio_rdreq <= 1'b0;
           end 
        else if (r_mdio_wrreq)
           begin
              word_no <= MDIOREG;
              addresses[MDIOREG] <= mdio_register[4:0];
              values[MDIOREG] <= mdio_wr_data;
              state <= MDIOWRREQ;
              wr_request <= 1'b1;
              r_mdio_wrreq <= 1'b0;
           end 
        else begin
           speed <= rd_data[15:14];
           duplex <= rd_data[13];
           
           if (init_required)
             begin
             wr_request <= 1;
             word_no <= (NUMREG - 4'd1); 
             last_allow_1Gbit <= allow_1Gbit;
             state  <= WRITING;
             init_required <= 1'b0;
             end
           else
             rd_request <= 1'b1;
           end
        end
        
      WRITING:
        begin
        if (word_no == 4'd1) begin
           state <= READING;
           init_busy <= 1'b0;
        end  else 
           wr_request <= 1;
        word_no <= word_no - 4'd1;		  
        end

      MDIORDREQ:
        begin
           mdio_rd_data <= rd_data;
           mdio_rw_busy <= 1'b0;
           state <= READING;
           word_no <= 4'd0;
        end
      
      MDIOWRREQ:
        begin
           mdio_rw_busy <= 1'b0;
           state <= READING;
           word_no <= 4'd0;
        end
      
      endcase
		
  else //!ready
    begin
    rd_request <= 0;
    wr_request <= 0;
    end
  end

end
        
        
        
        
//-----------------------------------------------------------------------------
//                        MDIO interface to PHY
//-----------------------------------------------------------------------------


mdio mdio_inst (
  .clock(clock), 
  .addr(addresses[word_no]), 
  .rd_request(rd_request),
  .wr_request(wr_request),
  .ready(ready),
  .rd_data(rd_data),
  .wr_data(values[word_no]),
  .mdio_pin(mdio_pin),
  .mdc_pin(mdc_pin)
  );  
  



  
  
endmodule
