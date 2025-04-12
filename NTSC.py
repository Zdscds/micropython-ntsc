import machine
import utime
import rp2
import array
import uctypes
from dma import DMA

@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
def blink():
    wrap_target()
    set(x, 28)       
    set(y, 8)
    
    label('Line')
    
    set(pins, 0) [8]
    label('high')
    set (pins, 1) [31]
    nop() [31]
    nop() [31]
    nop() [18] 
    jmp(x_dec, 'Line')         
    set(pins, 0) [5] 
    jmp (not_y, 'last') 
    set (x, 28)       
    jmp (y_dec, 'high') 
    label('last')
    set (pins, 0) [1]   
    set (pins, 1) [31]           # so in the 29 x 9 loop above we get 261 lines, then the last line takes place and then vsync
    nop ()[31]
    nop ()[31]
    nop ()[19]  #19
    set (pins, 0)
    set (x, 31) [31]
    
    label('syncV')         # The small inaccurate sync timings( Hsync being 4.5 instead of 4.7 ) and the fact that this is fake progressive scanning is probally whats causing vertical distortion, a remedy for this at the moment is fine tuning vertical sync. 
    jmp (x_dec, 'syncV') [4] # synchronization pulses for switching between odd/even NTSC field will be added in future
    #set x, 31 
    #jmp y--, syncV
    
    wrap()
    
@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW,out_init=rp2.PIO.OUT_LOW,out_shiftdir=rp2.PIO.SHIFT_LEFT,
    autopull=False,
    pull_thresh=32)
def video():
    wrap_target()
    set(pins, 0)
    label('end')
    set(pins, 0)
    wait(1, pin, 0)
    wait(0, pin, 0)  
    nop() [31]# backporch delays ( if the delay wasn't long enough the frame would have a left offset )
    nop() [31]
    set (y, 7) 
    set (x, 30)
    pull() [23]
    # decreased backporch since Hsyncs are around 5uS so we need 4.4 backporch   
    label('push_video') # 52.6uS
    out (pins, 1) [2] 
    #set (pins, 1) [2]
    jmp (x_dec, 'push_video')
    out (pins, 1)
    jmp (not_y, 'end')
    set (x, 30)
    pull()
    jmp (y_dec, 'push_video')
    wrap()
    
#两个状态机
#状态机0：VSYNC信号产生(0-3 pio0)，使用不同的pio可以保证程序存储空间足够。

#启动状态机

dmas = rp2.DMA() #actual number 0 to 11.
dma0 = DMA(dmas.channel)
ar = array.array("L", [255<<24|255<<16|255<<8|255 for i in range(2096)])

DMA.abort_all()    
image = uctypes.addressof(ar)
def test(x): #this irq should be triggered by an DMA.
    global dma0, image
    dma0.transfer(image)



"""
显示汉字代码
"""
def init_NTSC():
    global dmas, dma0, image
    sm = rp2.StateMachine(0, blink, freq=2_000_000, set_base=machine.Pin(0)) #125_000_000 / 62.5f 
    #状态机1：VID信号产生(4-7 pio1)
    sm2 = rp2.StateMachine(4, video, freq=125_000_000//6, set_base=machine.Pin(1), out_base=machine.Pin(1))
    #vram
    PIO1_BASE = 0x50300000
    PIO1_TX0 = PIO1_BASE + 0x010
    sm2.active(1)
    sm.active(1)
    dma0.config(read_addr = image,
            write_addr = PIO1_TX0,
            read_inc = True,
            write_inc = False,
            trans_count = 2096,
            treq_sel = dma0.DREQ_PIO1_TX0,
            data_size = 8)
    dma0.enable()
    dmas.irq(handler=test,hard=True)
"""
def writechar16(char, x, y):
    global ar
    ind = 128
    ar[ind+2] = 0xffffff0f
"""
def writechar16(char, x, y):
    global ind
    ind = x // 32 + y * 8
    mov = x % 32
    for i in range(16):
        if ind+8*i<2096 and ind+8*i>0:
            if mov > 15:
                if ind+8*i+1 < 2096:
                    ar[ind+8*i+1] ^= (char[i*2] << 24 | char[i*2+1] << 16) << (32 - mov)
            ar[ind+8*i] ^= (char[i*2] << 24 | char[i*2+1] << 16) >> mov
            
char =[0x08,0x80,0x08,0x80,0x08,0x80,0x11,0xFE,0x11,0x02,0x32,0x04,0x34,0x20,0x50,0x20,
0x91,0x28,0x11,0x24,0x12,0x24,0x12,0x22,0x14,0x22,0x10,0x20,0x10,0xA0,0x10,0x40]
char2 =[0x10,0x00,0x10,0xFC,0x10,0x04,0x10,0x08,0xFC,0x10,0x24,0x20,0x24,0x20,0x25,0xFE,
0x24,0x20,0x48,0x20,0x28,0x20,0x10,0x20,0x28,0x20,0x44,0x20,0x84,0xA0,0x00,0x40]
char3 =[0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
0x00,0x00,0x00,0x00,0x00,0x00,0x30,0x00,0x30,0x00,0x10,0x00,0x20,0x00,0x00,0x00]
char4 =[0x02,0x20,0x12,0x20,0x12,0x20,0x12,0x20,0x12,0x20,0xFF,0xFE,0x12,0x20,0x12,0x20,
0x12,0x20,0x12,0x20,0x13,0xE0,0x10,0x00,0x10,0x00,0x10,0x00,0x1F,0xFC,0x00,0x00]
char5=[0x00,0x00,0x1F,0xF0,0x11,0x10,0x11,0x10,0x1F,0xF0,0x11,0x10,0x11,0x10,0x1F,0xF0,
0x02,0x80,0x0C,0x60,0x34,0x58,0xC4,0x46,0x04,0x40,0x08,0x40,0x08,0x40,0x10,0x40]
init_NTSC()
x = 64
"""
Display scrolling chinese characters "你好,世界"
"""
writechar16(char, x+1, 32)
writechar16(char2, x+1+16, 32)
writechar16(char3, x+1+32, 32)
writechar16(char4, x+1+48, 32)
writechar16(char5, x+1+64, 32)
while True:
    writechar16(char, x+1, 32)
    writechar16(char2, x+1+16, 32)
    writechar16(char3, x+1+32, 32)
    writechar16(char4, x+1+48, 32)
    writechar16(char5, x+1+64, 32)
    
    writechar16(char, x, 32)
    writechar16(char2, x+16, 32)
    writechar16(char3, x+32, 32)
    writechar16(char4, x+48, 32)
    writechar16(char5, x+64, 32)
    
    utime.sleep_ms(50)
    x -= 1
