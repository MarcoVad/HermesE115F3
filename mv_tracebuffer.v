
module mv_tracebuffer(

   input        reset_n,
   input        rd_clock,
   input        wr_clock,
   input        enable,
   input        start_trig,
   input[31:0]  trace_data,
   input[7:0]   cmd_data,
   input        trace_req,
   output[7:0]  out_data,
   output       tracebuf_empty,
   output reg   running,
   output[7:0]  debug_trace_counter
);
   
wire fifo_wrfull;
wire fifo_rdreq = !tracebuf_empty & enable;

   
Debug_FIFO Debug_FIFO_inst(
    .wrclk(wr_clock),
    .data(trace_data),     // 32 bits
    .wrreq(running),
    .wrfull(fifo_wrfull),

    .rdclk(rd_clock),
    .q(out_data),  // 8 bits 
    .rdreq(fifo_rdreq),
    .rdempty(tracebuf_empty) );
   

// trace counter logic

reg [7:0] trace_counter;
reg [3:0] trace_state;
reg [7:0] cmd_data_r;

assign debug_trace_counter = trace_counter;

always @(posedge wr_clock or negedge reset_n)
begin
   if (!reset_n) begin
      running <= 1'b0;
      trace_counter <= 8'd0; 
      trace_state <= 4'd0;
      cmd_data_r <= 8'd0;      
   end else
   begin
      // crossing clock domains
      case (trace_state)
         4'd0:
            if (trace_req) begin
               trace_state <= 4'd1;
               cmd_data_r <= cmd_data;
            end
         4'd1:
            if (!trace_req) begin
               trace_state <= 4'd0;
               trace_counter <= cmd_data_r;
            end
      endcase
      
      if (trace_counter != 8'd0) begin
         if (start_trig && !running && tracebuf_empty)
            running <= 1'b1;
         else 
         if (fifo_wrfull) begin
            running <= 1'b0;
            trace_counter <= trace_counter - 8'd1;
         end
      end
    
    end
end

endmodule

