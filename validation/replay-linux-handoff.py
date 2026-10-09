#!/usr/bin/env python3
"""Exercise the actual Linux reconciliation code with a modeled device list.

Checks removal, held-state neutralization via the normal removal callback,
restoration without a udev event, idempotence and an edge during enumeration.
Real Steam reconnect and player-slot checks are separate hardware validation.
"""
from pathlib import Path
import subprocess
import tempfile

source = Path("src/joystick/linux/SDL_sysjoystick.c").read_text()
start = source.index("static bool flydigi_devices_changed;")
end = source.index("static void LINUX_JoystickDetect(void)", start)
implementation = source[start:end]
stubs = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stdio.h>
#define USB_VENDOR_FLYDIGI_V2 0x37d7
#define SDL_AssertJoysticksLocked() ((void)0)
typedef struct item { struct item *next; unsigned vendor,product; const char *name; } SDL_joylist_item;
static SDL_joylist_item *SDL_joylist;
static int SDL_LINUX_JoystickDriver;
static bool native_available,held,edge_in_scan;
static int removals,scans;
void LINUX_RefreshFlydigiDevices(void);
static bool SDL_JoystickHandledByAnotherDriver(void*d,unsigned v,unsigned p,int version,const char*n) {
 return native_available;
}
static void RemoveJoylistItem(SDL_joylist_item *item,SDL_joylist_item *prev) {
 assert(item->vendor==USB_VENDOR_FLYDIGI_V2);
 if(prev)prev->next=item->next;else SDL_joylist=item->next;
 // SDL_PrivateJoystickRemoved invokes ForceRecentering on open joysticks.
 held=false;removals++;free(item);
}
static void add(unsigned vendor) {
 SDL_joylist_item *i=calloc(1,sizeof(*i));i->vendor=vendor;i->name="test";
 i->next=SDL_joylist;SDL_joylist=i;
}
static int count(unsigned vendor) {int n=0;for(SDL_joylist_item*i=SDL_joylist;i;i=i->next)n+=i->vendor==vendor;return n;}
static void LINUX_ScanInputDevices(void) {
 scans++;
 if(!native_available && !count(USB_VENDOR_FLYDIGI_V2))add(USB_VENDOR_FLYDIGI_V2);
 if(edge_in_scan){edge_in_scan=false;LINUX_RefreshFlydigiDevices();}
}
'''
test = r'''
int main(void) {
 // Remove head, middle and tail fallback entries without losing other devices.
 add(USB_VENDOR_FLYDIGI_V2);add(1);add(USB_VENDOR_FLYDIGI_V2);add(2);add(USB_VENDOR_FLYDIGI_V2);
 held=true;native_available=true;
 LINUX_RefreshFlydigiDevices();LINUX_ReconcileFlydigiDevices();
 assert(removals==3 && !held && count(1)==1 && count(2)==1 && !count(USB_VENDOR_FLYDIGI_V2));
 LINUX_ReconcileFlydigiDevices();assert(scans==1);
 // Restore fallback when permission is revoked, without /dev/input changing.
 native_available=false;LINUX_RefreshFlydigiDevices();LINUX_ReconcileFlydigiDevices();
 assert(count(USB_VENDOR_FLYDIGI_V2)==1 && scans==2);
 LINUX_RefreshFlydigiDevices();LINUX_ReconcileFlydigiDevices();assert(count(USB_VENDOR_FLYDIGI_V2)==1);
 // An availability edge during enumeration must survive to the next detection.
 edge_in_scan=true;LINUX_RefreshFlydigiDevices();LINUX_ReconcileFlydigiDevices();
 assert(flydigi_devices_changed);LINUX_ReconcileFlydigiDevices();assert(!flydigi_devices_changed);
 for(int n=0;n<100;n++) {
  native_available=true;held=true;LINUX_RefreshFlydigiDevices();LINUX_ReconcileFlydigiDevices();
  assert(!held && !count(USB_VENDOR_FLYDIGI_V2));
  native_available=false;LINUX_RefreshFlydigiDevices();LINUX_ReconcileFlydigiDevices();
  assert(count(USB_VENDOR_FLYDIGI_V2)==1 && count(1)==1 && count(2)==1);
 }
 while(SDL_joylist){SDL_joylist_item *i=SDL_joylist;SDL_joylist=i->next;free(i);}
 puts("PASS: native/fallback handoff, held-state removal, repeated transitions, unchanged other devices");
}
'''
with tempfile.TemporaryDirectory() as temp:
    c=Path(temp)/"handoff.c";exe=Path(temp)/"handoff"
    c.write_text(stubs+implementation+test)
    subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Wno-unused-parameter",str(c),"-o",str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
