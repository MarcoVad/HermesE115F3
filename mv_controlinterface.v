
module mv_controlinterface #(parameter TRACEID)
(	
   input clock,
   input reset_n,
   
   // input data
   input [7:0] rx_data,
   input rx_strobe,
   input mdio_rw_busy,
   input spi_ready,
   input spi_rd_data,
   input spi_rd_strobe,
   input [15:0] mdio_rd_data, 
   input tracebuf_empty,
   input [7:0] trace_out_data,
  
   // output data
   output [7:0] tx_data,
   output tx_req,
   output reg [7:0] mdio_register,
   output reg [15:0] mdio_wr_data,
   output reg [7:0] io_data,
   output io_data_pulse,
   output spi_rw_req,  
   output CS_QDUCn,
   output CS_DDSn,
   output trace_req,
   output reg mdio_rd_request,
   output reg mdio_wr_request,
   output reg [7:0] codec_config,
   
   // debug
   output [7:0] debug_bytecnt,
   output [2:0] debug_mdio_state
);

assign debug_bytecnt = bytecnt;
assign debug_mdio_state = mdio_state;

reg [7:0] opcode;
reg [7:0] datalen;
reg [7:0] bytecnt;
reg [2:0] mdio_state;
reg [3:0] io_pulse_cnt;
reg rx_strobe_dt; 

localparam OP_NONE = 8'd0;
localparam OP_IO = 8'd1;
localparam OP_QDUC = 8'd2;
localparam OP_DDS = 8'd3;
localparam OP_MDIORD = 8'd10;
localparam OP_MDIOWR = 8'd11;
localparam OP_TRACE = 8'd12;
localparam OP_CODEC = 8'd13;

always @(posedge clock or negedge reset_n)
begin
   if (!reset_n)
   begin
       opcode <= 8'd0;
       bytecnt <= 8'd0;
       datalen <= 8'd0; 
       mdio_state <= 3'd0;
       io_pulse_cnt <= 4'd0;
   end
   else begin
     rx_strobe_dt <= rx_strobe;
     if (rx_strobe)
     begin
       case (bytecnt)
       8'd0: opcode <= rx_data;
       8'd1: datalen <= rx_data;
       8'd2: begin
          if (opcode==OP_MDIORD | opcode==OP_MDIOWR) mdio_register <= rx_data;
          else if (opcode==OP_IO) begin
             io_data <= rx_data;
             io_pulse_cnt <= 4'd1;
          end
          else if (opcode==OP_CODEC) codec_config <= rx_data;
       end
       8'd3: begin
          if (opcode==OP_MDIORD) mdio_rd_request <= 1'b1;
          else if (opcode==OP_MDIOWR) mdio_wr_data[15:8] <= rx_data;
       end
       8'd4: begin
          if (opcode==OP_MDIOWR) mdio_wr_data[7:0] <= rx_data; 
          if (opcode==OP_MDIOWR) mdio_wr_request <= 1'b1;
       end
       endcase
       
       bytecnt <= bytecnt + 8'd1;               
     end else   
     begin
       mdio_rd_request <= 1'b0;
       mdio_wr_request <= 1'b0;
        
       if (opcode == OP_MDIORD)
       begin
          case (mdio_state)
          3'd0: // waiting for mdio_rw_busy
             if (mdio_rw_busy) mdio_state <= 3'd1;
          3'd1: // waiting for end of mdio_rw_busy
             if (!mdio_rw_busy) mdio_state <= 3'd2;
          3'd2: // read high byte from mdio_rx_data
             mdio_state <= 3'd3;
          default: // read low byte from mdio_rx_data
             mdio_state <= 3'd0;
          endcase
       end;
        
       if (io_pulse_cnt != 4'd0) io_pulse_cnt <= io_pulse_cnt + 4'd1;
       
       if (bytecnt > (datalen+8'd1) & !init_data)
       begin
         bytecnt <= 8'd0;
         datalen <= 8'd0;           
       end
       
     end 
   end
end

wire init_data = (bytecnt < 8'd2);

// wiring for OP_IO
assign io_data_pulse = (io_pulse_cnt > 4'd8)? 1'b1: 1'b0;

// wiring for OP_QDUC and OP_DDS
wire spi_data = (opcode==OP_QDUC | opcode==OP_DDS) & !init_data;
wire spi_active = spi_data|!spi_ready;
assign spi_rw_req = spi_data & rx_strobe;
assign CS_QDUCn = (spi_active & opcode == OP_QDUC)? 1'b0: 1'b1;
assign CS_DDSn =  (spi_active & opcode == OP_DDS)? 1'b0: 1'b1;

// wiring for OP_TRACE
wire trace_active = (opcode==OP_TRACE) & !init_data;  
assign trace_req = (opcode==OP_TRACE) & !init_data & rx_strobe;

// wiring for OP_MDIORD and OP_MDIOWR
wire mdiord_active = (opcode==OP_MDIORD) & (bytecnt > 8'd2);  
wire mdiord_data = mdio_state > 3'd1;
wire [7:0] mdio_rd_data_byte = (mdio_state==3'd2)? mdio_rd_data[15:8] : mdio_rd_data[7:0]; 


assign tx_data = (spi_active)? spi_rd_data : 
                      (mdiord_active)? mdio_rd_data_byte : 
                      (!tracebuf_empty)? trace_out_data: 
                      (trace_active)?(8'h20 + TRACEID):
                      rx_data;
assign tx_req = (spi_active)? spi_rd_strobe : 
                     (mdiord_active)? mdiord_data:
                     (!tracebuf_empty)? 1'b1: 
                     rx_strobe;

endmodule

