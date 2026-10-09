#!/usr/bin/env python3
"""Replay button states through SDL's actual V2 parser without opening hardware.

The parser is extracted from the selected source file, so this can test both
baseline and candidate builds. Hardware enumeration and Steam UI are separate tests.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

parser=argparse.ArgumentParser()
parser.add_argument('--source',type=Path,default=Path('src/joystick/hidapi/SDL_hidapi_flydigi.c'))
parser.add_argument('--include',type=Path,default=Path('include'))
parser.add_argument('--capture',type=Path,help='Replay raw button-change reports from Flydigi Control')
args=parser.parse_args()
source=args.source.read_text()
start=source.index('static void HIDAPI_DriverFlydigi_HandleStatePacketV2(')
end=source.index('\nstatic void ',start+1)
handler=source[start:end]
preamble=r'''
#include <SDL3/SDL.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define SDL_GAMEPAD_NUM_BASE_FLYDIGI_BUTTONS 15
#define SDL_GAMEPAD_BUTTON_FLYDIGI_M1 11
#define SDL_GAMEPAD_BUTTON_FLYDIGI_M2 12
#define SDL_GAMEPAD_BUTTON_FLYDIGI_M3 13
#define SDL_GAMEPAD_BUTTON_FLYDIGI_M4 14
#define LOAD16(a,b) ((Sint16)((Uint16)(a) | ((Uint16)(b)<<8)))
#undef SDL_memcpy
#define SDL_memcpy memcpy
static bool buttons[21];
typedef struct {
    Uint8 last_state[64];
    bool has_cz,has_lmrm,has_circle,has_turbo,sensors_enabled;
    Uint64 sensor_timestamp_ns,sensor_timestamp_step_ns;
    float gyroScale,accelScale;
} SDL_DriverFlydigi_Context;
Uint64 SDL_GetTicksNS(void) {return 1;}
static void SDL_SendJoystickHat(Uint64 t,SDL_Joystick*j,Uint8 h,Uint8 v) {}
static void SDL_SendJoystickAxis(Uint64 t,SDL_Joystick*j,Uint8 a,Sint16 v) {}
static void SDL_SendJoystickSensor(Uint64 t,SDL_Joystick*j,SDL_SensorType s,Uint64 st,const float*v,int n) {}
static void SDL_SendJoystickButton(Uint64 t,SDL_Joystick*j,Uint8 b,bool v) {assert(b<21);buttons[b]=v;}
static float HIDAPI_RemapVal(float a,float b,float c,float d,float e) {return d+(a-b)*(e-d)/(c-b);}
'''
main=r'''
static void check(int extra,int fn) {
    assert(buttons[11]==!!(extra&4)); assert(buttons[12]==!!(extra&8));
    assert(buttons[13]==!!(extra&16)); assert(buttons[14]==!!(extra&32));
    assert(buttons[15]==!!(extra&1)); assert(buttons[16]==!!(extra&2));
    assert(buttons[17]==!!(extra&64)); assert(buttons[18]==!!(extra&128));
    assert(buttons[19]==!!(fn&1)); assert(buttons[20]==!!(fn&2));
}
int main(void) {
    SDL_DriverFlydigi_Context ctx={.has_cz=true,.has_lmrm=true,.has_circle=true,.has_turbo=true};
    Uint8 packet[32]={0x5a,0xa5,0xef};
    unsigned count=0;
    for(int extra=0;extra<256;extra++) for(int fn=0;fn<16;fn++) {
        packet[13]=extra;packet[14]=fn;
        HIDAPI_DriverFlydigi_HandleStatePacketV2(NULL,&ctx,packet,32);
        check(extra,fn);count++;
        // Repeated reports, then independently release the function buttons.
        HIDAPI_DriverFlydigi_HandleStatePacketV2(NULL,&ctx,packet,32);
        check(extra,fn);count++;
        packet[14]=0;
        HIDAPI_DriverFlydigi_HandleStatePacketV2(NULL,&ctx,packet,32);
        check(extra,0);count++;
    }
    packet[13]=0;
    HIDAPI_DriverFlydigi_HandleStatePacketV2(NULL,&ctx,packet,32);check(0,0);
    printf("PASS: %u mixed, repeated and release reports; Turbo and Fn independent; existing extras unchanged\n",count+1);
}
'''
if args.capture:
    records = [json.loads(line) for line in args.capture.read_text().splitlines()]
    packets = [bytes.fromhex(r['raw']) for r in records if r.get('event') == 'buttons']
    if not packets or any(len(p) != 32 or p[:3] != bytes.fromhex('5aa5ef') for p in packets):
        raise ValueError('Capture must contain complete 32-byte V2 input reports')
    declarations = ',\n'.join('{' + ','.join(str(v) for v in packet) + '}' for packet in packets)
    main = main[:main.index('int main(void)')] + r'''
static Uint8 captured[][32] = {CAPTURE};
int main(void) {
    SDL_DriverFlydigi_Context ctx={.has_cz=true,.has_lmrm=true,.has_circle=true,.has_turbo=true};
    for (unsigned i=0; i<sizeof(captured)/sizeof(captured[0]); i++) {
        HIDAPI_DriverFlydigi_HandleStatePacketV2(NULL,&ctx,captured[i],32);
        check(captured[i][13],captured[i][14]);
    }
    printf("PASS: %zu captured physical reports; all ten extra-button states agree\n",
           sizeof(captured)/sizeof(captured[0]));
}
'''.replace('CAPTURE', declarations)
with tempfile.TemporaryDirectory() as folder:
    folder=Path(folder);c=folder/'replay.c';exe=folder/'replay'
    c.write_text(preamble+handler+main)
    subprocess.run(['cc','-std=c11','-I'+str(args.include.resolve()),str(c),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
