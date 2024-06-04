module mv_spimaster(
	input         clk,
	input         reset_n,
						
   // reading and writing happens simultaniously, triggered by rw request 
   input         rw_req,
   input [7:0]   wr_data,
   output reg [7:0]  rd_data,
   output        rd_strobe,
   output        ready,

	// IO pins
	output reg    sclk,
	output reg    mosi,
	input         miso
);
//----------------------------------------------------------------

reg [7:0]	wr_buf;
reg [3:0]   bit_cnt;
reg [3:0]  	state;

localparam 
    IDLE      = 4'd1,
    SHIFT_OUT = 4'd2,
    SHIFT_IN  = 4'd4,
    DONE      = 4'd8;

always@(posedge clk or negedge reset_n)
begin
	if (!reset_n)
	begin
		state <= IDLE;
	end
	else begin
     case (state)
  
     IDLE:
        begin
           sclk <= 1'b1;
           bit_cnt <= 4'd8;
           if (rw_req == 1'b1)
           begin
              wr_buf <= wr_data;
              state <= SHIFT_OUT;
           end
        end	

     SHIFT_OUT:
        begin
           if (bit_cnt == 4'd0)
           begin
              state <= DONE;
           end
           else
              begin
                  mosi <= wr_buf[7];	
                  wr_buf <= {wr_buf[6:0], 1'b0};
                  sclk <= 1'b0;
                  state <= SHIFT_IN; 
              end
        end

     SHIFT_IN:
        begin	
           rd_data <= {rd_data[6:0], miso};
           bit_cnt <= bit_cnt - 1'd1;
           sclk <= 1'b1;
           state <= SHIFT_OUT; 
        end

      DONE:
         begin
           mosi <= 1'd0;               
           state <= IDLE;
         end

     default:
        state <= IDLE;

     endcase
	end
end



assign ready = (state == IDLE);
assign rd_strobe = (state == DONE);

endmodule
