#!/usr/bin/env python3
"""Verify the actual rumble callback's HID framing and start/stop intensities."""
from pathlib import Path
import subprocess
import tempfile
s=Path('src/joystick/hidapi/SDL_hidapi_flydigi.c').read_text()
a=s.index('static bool HIDAPI_DriverFlydigi_RumbleJoystick(')
b=s.index('static bool HIDAPI_DriverFlydigi_RumbleJoystickTriggers(',a)
preamble=r'''
#include <stdbool.h>
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t Uint8;typedef uint16_t Uint16;
typedef struct {int vendor_id,product_id;} SDL_HIDAPI_Device;
typedef struct {int unused;} SDL_Joystick;
#define USB_VENDOR_FLYDIGI_V1 0x04b4
#define USB_PRODUCT_FLYDIGI_V2_VADER 0x2401
#define FLYDIGI_V1_CMD_REPORT_ID 5
#define FLYDIGI_V1_HAPTIC_COMMAND 15
#define FLYDIGI_V2_CMD_REPORT_ID 3
#define FLYDIGI_V2_MAGIC1 0x5a
#define FLYDIGI_V2_MAGIC2 0xa5
#define FLYDIGI_V2_HAPTIC_COMMAND 0x12
static Uint8 sent[32];static int size;static bool fail;
static int SDL_HIDAPI_SendRumble(SDL_HIDAPI_Device*d,const Uint8*p,int n){assert(n<=32);memcpy(sent,p,n);size=n;return fail?-1:n;}
static bool SDL_SetError(const char*s){return false;}
'''
main=r'''
int main(void){
 SDL_HIDAPI_Device d={0x37d7,0x2401};
 assert(HIDAPI_DriverFlydigi_RumbleJoystick(&d,NULL,0x7fff,0x3fff));
 const Uint8 expected[]={0,0x5a,0xa5,0x12,6,0x7f,0x3f,0,0,0};
 assert(size==sizeof(expected) && !memcmp(sent,expected,size));
 assert(HIDAPI_DriverFlydigi_RumbleJoystick(&d,NULL,0,0));
 assert(sent[0]==0 && sent[5]==0 && sent[6]==0);
 // Other V2 models keep numbered reports; V1 framing stays untouched.
 d.product_id=0x2402;
 assert(HIDAPI_DriverFlydigi_RumbleJoystick(&d,NULL,0xffff,0xffff));
 assert(sent[0]==3 && sent[5]==255 && sent[6]==255);
 d.vendor_id=USB_VENDOR_FLYDIGI_V1;
 assert(HIDAPI_DriverFlydigi_RumbleJoystick(&d,NULL,0xffff,0x8000));
 assert(size==4 && sent[0]==5 && sent[1]==15 && sent[2]==255 && sent[3]==128);
 fail=true;assert(!HIDAPI_DriverFlydigi_RumbleJoystick(&d,NULL,1,1));
 puts("PASS: Vader unnumbered rumble, start/stop levels, other models unchanged, write failure");
}
'''
with tempfile.TemporaryDirectory() as folder:
 c=Path(folder)/'rumble.c';exe=Path(folder)/'rumble'
 c.write_text(preamble+s[a:b]+main)
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Wno-unused-parameter',str(c),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
