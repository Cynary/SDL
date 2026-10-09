#!/usr/bin/env python3
"""Check deferred initialization and query timing using the driver's actual C."""
from pathlib import Path
import subprocess
import tempfile
s=Path('src/joystick/hidapi/SDL_hidapi_flydigi.c').read_text()
a=s.index('static bool HIDAPI_DriverFlydigi_InitInfoV2(')
b=s.index('static bool HIDAPI_DriverFlydigi_InitDevice(',a)
init=s[a:b]
a=s.index('    if (device->vendor_id == USB_VENDOR_FLYDIGI_V2 && !joystick &&')
b=s.index('    if (device->vendor_id == USB_VENDOR_FLYDIGI_V2 && joystick)',a)
recovery=s[a:b]
preamble=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef uint8_t Uint8; typedef uint16_t Uint16; typedef uint64_t Uint64;
#define USB_VENDOR_FLYDIGI_V2 0x37d7
#define USB_PRODUCT_FLYDIGI_V2_APEX 0x2402
#define USB_PRODUCT_FLYDIGI_V2_VADER 0x2401
#define LOAD16(a,b) ((Uint16)(a)|((Uint16)(b)<<8))
typedef struct {void *context;int vendor_id,product_id;} SDL_HIDAPI_Device;
typedef struct {Uint16 firmware_version;bool wireless,initialized_v2;Uint8 deviceID;Uint64 next_discovery_query;} SDL_DriverFlydigi_Context;
static int info_queries,status_queries,identities;
static Uint64 ticks;
static bool write_ok;
static bool SDL_SetError(const char*s){return false;}
static Uint64 SDL_GetTicks(void){return ticks;}
static bool SDL_HIDAPI_Flydigi_SendInfoRequest(SDL_HIDAPI_Device*d){info_queries++;return write_ok;}
static bool SDL_HIDAPI_Flydigi_SendStatusRequest(SDL_HIDAPI_Device*d){status_queries++;return write_ok;}
static void HIDAPI_DriverFlydigi_UpdateDeviceIdentity(SDL_HIDAPI_Device*d){identities++;}
'''
main=r'''
int main(void){
 SDL_DriverFlydigi_Context ctx={0};SDL_HIDAPI_Device dev={&ctx,USB_VENDOR_FLYDIGI_V2,USB_PRODUCT_FLYDIGI_V2_VADER};
 Uint8 info[32]={0};
 // Receiver exists but the controller is off: write/reply failure is not fatal.
 assert(HIDAPI_DriverFlydigi_InitControllerV2(&dev));assert(info_queries==1 && !ctx.initialized_v2);
 recover(&dev,NULL,999);assert(info_queries==1);
 recover(&dev,NULL,1000);assert(info_queries==2 && status_queries==0);
 recover(&dev,NULL,1001);assert(info_queries==2);
 assert(!HIDAPI_DriverFlydigi_InitInfoV2(&dev,info,5));
 assert(!HIDAPI_DriverFlydigi_InitInfoV2(&dev,info,32));assert(!ctx.initialized_v2 && !identities);
 // A valid later reply initializes identity before requesting native permission.
 info[5]=5;info[6]=2;info[15]=0x71;info[16]=0x50;write_ok=true;
 assert(HIDAPI_DriverFlydigi_InitInfoV2(&dev,info,32));
 assert(ctx.initialized_v2 && ctx.wireless && identities==1 && status_queries==1);
 recover(&dev,NULL,2000);assert(info_queries==3 && status_queries==2);
 // Once opened, ordinary heartbeat owns traffic; no discovery query storm.
 recover(&dev,(void*)1,9000);assert(info_queries==3 && status_queries==2);
 recover(&dev,NULL,9000);assert(info_queries==4 && status_queries==3);
 puts("PASS: controller-off initialization, delayed valid reply, bounded retries, no probing open joystick");
}
'''
wrapper='static void recover(SDL_HIDAPI_Device *device,void *joystick,Uint64 now){SDL_DriverFlydigi_Context *ctx=device->context;\n'+recovery+'}\n'
with tempfile.TemporaryDirectory() as folder:
 c=Path(folder)/'reconnect.c';exe=Path(folder)/'reconnect'
 c.write_text(preamble+init+wrapper+main)
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Wno-unused-parameter',str(c),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
