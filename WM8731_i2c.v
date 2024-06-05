// WM8731_i2c.v
//
// Copyright (C) 2013 Joe Martin K5SO
//                    k5so@valornet.command
//
// This module sequences commands to the i2c MASTER module which in turn controls the i2c bus
/*
   Updated by PE1NWK
   
   * Updated to support the WM8731 codec
   * removed Penny and Mercury stuff
   
   Notes: 
   * The WM8731 on the A-E115FB board is wired with MODE and CSB pins to ground.
     That means that the configuration interface is I2C and device address is 0011010.
   * The WM8731 is write only device. Therefore you cannot read back the configuration registers. 
           
*/

 
module WM8731_i2c(
   input wire clock,               // state machine clock
   input wire I2C_clock,               // 800 KHz (768kHz) clock from which to derive the 200 KHz (192kHz) i2c bus clock
   input reg reset_n,                  // reset
   inout wire sda,
   output wire scl,
   input reg mic_boost,
   input reg line_in,
   input [4:0] line_gain,

   //debug
   output [31:0] trace_data,
   output reg running
   );
   
localparam CODEC_ADDR = 7'b0011010;
localparam NUMREG = 4'd8;

logic [12:0] codec_init [NUMREG-1:0];
wire[12:0] wr_data = codec_init[word_no];

//state machine  
localparam 
   IDLE = 2'd0, 
   WRITING = 2'd1;

reg [1:0] state;
reg [3:0] word_no;
reg init_required;
reg update_required;
reg init_request;
reg prev_mic_boost;
reg prev_line_in;
reg [4:0] prev_line_gain;
reg wr_request;
reg busy;
wire rw = 1'b0;

assign trace_data = {
      running, update_required, reset_n, wr_request, busy, init_required, sda, scl,
      word_no, 2'b0, state,
      3'b0, wr_data};    

always @(posedge I2C_clock or negedge reset_n)  
begin
   if (!reset_n)
   begin
      running <= 1'b0;
      init_request <= 1'b1;
      wr_request <= 0;
   end else
   begin
      update_required <= (line_gain != prev_line_gain) || (mic_boost != prev_mic_boost) || (line_in != prev_line_in); 
      if (init_request || update_required)  
      begin
         init_request <= 1'b0;
         init_required <= 1'b1;
         running <= 1'b1;
         
         //setup registers for the Audio codec
         codec_init[7] = {4'hF, 9'h00};                   // chip reset
         codec_init[6] = {4'h9, 9'h01};                   // set digitial interface active
         codec_init[5] = {4'h6, 9'h00};                   // all chip power ON
         codec_init[4] = {4'h7, 9'h02};                   // slave, 16 bit, I2C
         codec_init[3] = {4'h8, 9'h00};                   // 48k, normal mode
         codec_init[2] = {4'h5, 9'h00};                   // turn D/A mute OFF
         codec_init[1] = line_in?                         // line or mic imput / mic boost
            {4'h4, 9'h10}: 
            {4'h4, 8'h0A, mic_boost};     
         codec_init[0] = {4'h0, 4'h0, line_gain};         // set line-in gain
      end
      
      if (!busy)
      begin
         if (!wr_request)
         case (state)
            IDLE:
            begin
               if (init_required)
               begin
                  init_required <= 1'b0;
                  wr_request <= 1;
                  if (update_required) begin
                     word_no <= 4'd1;
                     prev_line_gain <= line_gain;
                     prev_mic_boost <= mic_boost; 
                     prev_line_in <= line_in; 
                  end 
                  else begin
                     word_no <= (NUMREG - 4'd1);
                  end
                  
                  state <= WRITING;
               end
            end
            
            WRITING:
            begin
               if (word_no == 4'd0) begin
                  state <= IDLE;
                  running <= 1'b0;
                  init_required <= 1'b0;
               end  
               else begin 
                  wr_request <= 1;
                  word_no <= word_no - 4'd1;
               end
            end
            
            default:
               state <= IDLE;
         endcase
         // else, wr_request has been set, wait for busy to react... 
         
      end else //busy
      begin
         wr_request <= 0;
      end
   end

end


i2c_master master_inst(
      .I2C_clock(I2C_clock), 
      .reset_n(reset_n), 
      .ena(wr_request), 
      .addr(CODEC_ADDR), 
      .rw(rw), 
      .data_wr({3'b0, wr_data}), 
      .busy(busy), 
      .ack_error(), 
      .sda(sda), 
      .scl(scl) 
      );

                                    
endmodule
