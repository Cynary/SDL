#!/usr/bin/env python3
"""Replay battery startup and the captured transient zero against driver C."""
from pathlib import Path
import subprocess
import tempfile
s = Path('src/joystick/hidapi/SDL_hidapi_flydigi.c').read_text()
start = s.index('static void HIDAPI_DriverFlydigi_SendCachedPowerInfo(')
end = s.index('static bool SDL_HIDAPI_Flydigi_SendStatusRequest(', start)
preamble = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef uint8_t Uint8; typedef uint64_t Uint64;
typedef enum {SDL_POWERSTATE_UNKNOWN, SDL_POWERSTATE_ON_BATTERY,
 SDL_POWERSTATE_CHARGING, SDL_POWERSTATE_CHARGED} SDL_PowerState;
typedef struct {int unused;} SDL_Joystick;
typedef struct {bool battery_valid;Uint8 battery_raw;Uint64 battery_zero_deadline;
 bool battery_zero_query_sent;} SDL_DriverFlydigi_Context;
typedef struct {void *context;} SDL_HIDAPI_Device;
static Uint64 ticks;
static int events, queries, percent;
static SDL_PowerState state;
static Uint64 SDL_GetTicks(void){return ticks;}
static void SDL_SendJoystickPowerInfo(SDL_Joystick*j,SDL_PowerState s,int p){events++;state=s;percent=p;}
static bool SDL_HIDAPI_Flydigi_SendInfoRequest(SDL_HIDAPI_Device*d){queries++;return false;}
'''
main = r'''
int main(void){
 SDL_DriverFlydigi_Context ctx={0};SDL_HIDAPI_Device device={&ctx};SDL_Joystick joy;
 Uint8 data[32]={0};
 // A reply before open must survive until the joystick exists.
 data[11]=2;HIDAPI_DriverFlydigi_HandleInfoResponse(NULL,&ctx,data,32);
 assert(ctx.battery_valid && !events);
 HIDAPI_DriverFlydigi_SendCachedPowerInfo(&joy,&ctx);
 assert(events==1 && percent==40 && state==SDL_POWERSTATE_ON_BATTERY);
 // Captured sequence: zero, then 40% 1.16 seconds later. No zero event.
 ticks=100;data[11]=0;HIDAPI_DriverFlydigi_HandleInfoResponse(&joy,&ctx,data,32);
 assert(events==1);
 ticks=1260;data[11]=2;HIDAPI_DriverFlydigi_HandleInfoResponse(&joy,&ctx,data,32);
 assert(percent==40 && !ctx.battery_zero_deadline);
 HIDAPI_DriverFlydigi_ConfirmBattery(&device,2200);assert(!queries);
 // Real empty battery still reports zero after confirmation. A failed query
 // is sent once, never on every input poll; normal heartbeats remain available.
 ticks=3000;data[11]=0;HIDAPI_DriverFlydigi_HandleInfoResponse(&joy,&ctx,data,32);
 HIDAPI_DriverFlydigi_ConfirmBattery(&device,4999);assert(!queries);
 for(int i=5000;i<9000;i++)HIDAPI_DriverFlydigi_ConfirmBattery(&device,i);
 assert(queries==1 && percent==40);
 ticks=9000;HIDAPI_DriverFlydigi_HandleInfoResponse(&joy,&ctx,data,32);
 assert(percent==0 && !ctx.battery_zero_deadline);
 ticks++;HIDAPI_DriverFlydigi_HandleInfoResponse(&joy,&ctx,data,32);
 assert(percent==0 && !ctx.battery_zero_deadline);
 // Unknown is not empty; charging/full transitions need no debounce.
 data[11]=0xf0;HIDAPI_DriverFlydigi_HandleInfoResponse(&joy,&ctx,data,32);
 assert(percent==-1 && state==SDL_POWERSTATE_UNKNOWN);
 data[11]=0x13;HIDAPI_DriverFlydigi_HandleInfoResponse(&joy,&ctx,data,32);
 assert(percent==60 && state==SDL_POWERSTATE_CHARGING);
 data[11]=0x20;HIDAPI_DriverFlydigi_HandleInfoResponse(&joy,&ctx,data,32);
 assert(percent==100 && state==SDL_POWERSTATE_CHARGED);
 // Zero on first contact stays unknown until confirmed, not falsely full.
 ctx=(SDL_DriverFlydigi_Context){0};ticks=10000;data[11]=0;
 HIDAPI_DriverFlydigi_HandleInfoResponse(NULL,&ctx,data,32);assert(!ctx.battery_valid);
 ticks=12000;HIDAPI_DriverFlydigi_HandleInfoResponse(NULL,&ctx,data,32);
 HIDAPI_DriverFlydigi_SendCachedPowerInfo(&joy,&ctx);assert(percent==0);
 puts("PASS: cached initial battery, transient zero, confirmed empty, bounded query, unknown and charging");
}
'''
with tempfile.TemporaryDirectory() as folder:
    c=Path(folder)/'battery.c';exe=Path(folder)/'battery'
    c.write_text(preamble+s[start:end]+main)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Wno-unused-parameter',str(c),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
