
module mv_uart(
   input clock,
   input reset_n,
  
   // TxD 
   input tx_clock,
   input [7:0] tx_data, 
   input tx_req,
   output fifo_wrfull,
   output tx_ready,

   // RxD
   output reg [7:0] rx_data,
   output reg rx_strobe, 

   // hardware 
   output reg txd,
   input rxd,
   
   // debug
   output reg [2:0] debug_rx_state,
   output reg [3:0] debug_rx_bitcnt
);

// ================================= //

reg [2:0] tx_state;
reg [3:0] tx_bitcnt;
wire [7:0] fifo_data;
wire fifo_rdreq;
wire fifo_rdempty;


Uart_FIFO Uart_FIFO_inst(
    .wrclk(!tx_clock),
    .data(tx_data),
    .wrreq(tx_req),
    .wrfull(fifo_wrfull),

    .rdclk(clock),
    .q(fifo_data),
    .rdreq(fifo_rdreq),
    .rdempty(fifo_rdempty) );


always @ (posedge clock or negedge reset_n)
begin
   if (!reset_n) begin
      tx_state <= 3'd0; 
      txd <= 1'b1; // idle
   end 
   else begin
      case (tx_state)
      3'd0: begin
          if (!fifo_rdempty) begin
           tx_state <= 3'd1; 
           tx_bitcnt <= 4'd0;   
           txd <= 1'b0; // start bit      
          end
      end

      3'd2: begin
        tx_state <= (tx_bitcnt == 4'd8)? 3'd4: 3'd3; 
      end

      3'd3: begin
        txd <= fifo_data[tx_bitcnt]; // data bits  
        tx_bitcnt <= tx_bitcnt + 4'd1; 
        tx_state <= 3'd1; 
      end

      3'd4: begin
        txd <= 1'b1; // stop bit    
        tx_state <= 3'd5; 
      end
      
      3'd6: tx_state <= 3'd0;
      
      default: tx_state <= tx_state + 3'd1;
      endcase
   end
end

assign fifo_rdreq = (tx_state == 3'd1) & (tx_bitcnt == 4'd0);
assign tx_ready = !fifo_wrfull;

// ================================= //

reg [2:0] rx_state;
reg [3:0] rx_bitcnt;
reg [8:0] rx_data_temp; // holds 8 data bits and the stop bit

always @ (posedge clock or negedge reset_n)
begin
   if (!reset_n) begin
      rx_state <= 3'd0; 
      rx_data_temp <= 8'd0;
      rx_bitcnt <= 4'd0;   
   end 
   else begin
      case (rx_state)
      3'd0: begin
          rx_strobe <= 1'b0;
          rx_bitcnt <= 4'd0;   
          if (rxd == 1'b0) begin
           rx_state <= 3'd1; 
          end
      end

      3'd2: begin
         if (rx_bitcnt == 4'd9) begin
            rx_state <= 3'd0;
            rx_bitcnt <= 4'd0;   
            rx_data <= rx_data_temp[7:0];
            rx_strobe <= rx_data_temp[8];  // strobe is actually equal to the stop bit, it should be '1'
                                           // if not, we have a framing error and drop the data
         end else
            rx_state <= 3'd3; 
      end

      3'd4: begin
        rx_data_temp[rx_bitcnt] <= rxd; // data and stop bits  
        rx_bitcnt <= rx_bitcnt + 4'd1; 
        rx_state <= 3'd2; 
      end

      default: rx_state <= rx_state + 3'd1;
      
      endcase
   end
end

assign debug_rx_state = rx_state;
assign debug_rx_bitcnt = rx_bitcnt;
   
   
endmodule
