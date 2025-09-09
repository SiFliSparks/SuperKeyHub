#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
硬件监控模块
"""

import os, sys, math, time
import psutil

def _try_import(name):
    try: return __import__(name)
    except Exception: return None

wmi    = _try_import("wmi")
clr    = _try_import("clr")
pynvml = _try_import("pynvml")

class LHM:
    def __init__(self):
        self.ok=False; self.SensorType=None; self.HardwareType=None; self.pc=None
        if not clr: return
        try:
            # 多路径搜索DLL
            search_paths = [
                "libs/LibreHardwareMonitorLib.dll",  # 标准位置
                "LibreHardwareMonitorLib.dll",       # 根目录
                os.path.join(os.path.dirname(__file__), "LibreHardwareMonitorLib.dll"),  # 当前目录
                "LibreHardwareMonitorLib"  # 尝试直接引用
            ]
            
            for dll_path in search_paths:
                try: 
                    clr.AddReference(dll_path)
                    break
                except Exception: 
                    continue
            else:
                # 如果所有路径都失败
                return
                
            from LibreHardwareMonitor.Hardware import Computer, SensorType, HardwareType
            self.SensorType=SensorType; self.HardwareType=HardwareType
            pc=Computer(); pc.IsCpuEnabled=pc.IsGpuEnabled=pc.IsMemoryEnabled=pc.IsMotherboardEnabled=True
            pc.Open(); self.pc=pc; self.ok=True
        except Exception:
            self.ok=False
    
    def _update(self):
        if not self.ok: return
        for hw in self.pc.Hardware:
            hw.Update()
            for sub in hw.SubHardware: sub.Update()
    
    def cpu_name(self):
        if not self.ok: return None
        for hw in self.pc.Hardware:
            if hw.HardwareType==self.HardwareType.Cpu: return hw.Name
        return None
    
    def cpu_read(self):
        if not self.ok: return {}
        self._update()
        usage=temp=power=None; clocks=[]
        for hw in self.pc.Hardware:
            if hw.HardwareType!=self.HardwareType.Cpu: continue
            for s in hw.Sensors:
                st=s.SensorType; name=s.Name or ""
                val=float(s.Value) if s.Value is not None else None
                if val is None or (isinstance(val,float) and math.isnan(val)): continue
                if st==self.SensorType.Load and "Total" in name: usage=val
                elif st==self.SensorType.Temperature and any(k in name for k in["Package","Tctl","Tdie"]): temp=val
                elif st==self.SensorType.Power and any(k in name for k in["Package","CPU"]): power=val
                elif st==self.SensorType.Clock and ("Core #" in name or "Core" in name): clocks.append(val)
        clock=sum(clocks)/len(clocks) if clocks else None
        return {"usage":usage,"temp":temp,"power":power,"clock_mhz":clock}
    
    def list_gpus(self):
        if not self.ok: return []
        return [hw.Name for hw in self.pc.Hardware
                if hw.HardwareType in (self.HardwareType.GpuNvidia,self.HardwareType.GpuAmd,self.HardwareType.GpuIntel)]
    
    def gpu_read(self, idx=0):
        if not self.ok: return {}
        self._update()
        gpus=[hw for hw in self.pc.Hardware if hw.HardwareType in(
            self.HardwareType.GpuNvidia,self.HardwareType.GpuAmd,self.HardwareType.GpuIntel)]
        if not gpus or idx>=len(gpus): return {}
        hw=gpus[idx]; data={"name":hw.Name}; mu=mt=None
        for s in hw.Sensors:
            st=s.SensorType; name=s.Name or ""
            val=float(s.Value) if s.Value is not None else None
            if val is None or (isinstance(val,float) and math.isnan(val)): continue
            if st==self.SensorType.Load and ("Core" in name or name=="GPU Core"): data["util"]=val
            elif st==self.SensorType.Temperature and ("Core" in name or name=="GPU Core"): data["temp"]=val
            elif st==self.SensorType.Clock and ("Core" in name or name=="GPU Core"): data["clock_mhz"]=val
            elif st in (self.SensorType.Data,self.SensorType.SmallData):
                if "Memory Used" in name: mu=val
                elif "Memory Total" in name: mt=val
            elif st==self.SensorType.Power and "GPU" in name: data["power"]=val
        if mu is not None: data["mem_used_b"]=mu*1024*1024
        if mt is not None: data["mem_total_b"]=mt*1024*1024
        return data
    
    def memory_read(self):
        if not self.ok: return {}
        self._update(); out={}
        for hw in self.pc.Hardware:
            if hw.HardwareType==self.HardwareType.Memory:
                for s in hw.Sensors:
                    st=s.SensorType; name=s.Name or ""
                    val=float(s.Value) if s.Value is not None else None
                    if val is None or (isinstance(val,float) and math.isnan(val)): continue
                    if st==self.SensorType.Load and name=="Memory": out["percent"]=val
                    elif st in (self.SensorType.Data,self.SensorType.SmallData):
                        if "Used Memory" in name: out["used_b"]=val*1024*1024
                        elif "Available Memory" in name: out["avail_b"]=val*1024*1024
                        elif "Total Memory" in name: out["total_b"]=val*1024*1024
        return out

class NVML:
    def __init__(self):
        self.ok=False; self.nv=pynvml; self.count=0
        if not self.nv: return
        try:
            self.nv.nvmlInit(); self.count=self.nv.nvmlDeviceGetCount(); self.ok=self.count>0
        except Exception: self.ok=False
    
    def list_gpus(self):
        if not self.ok: return []
        out=[]
        for i in range(self.count):
            try:
                h=self.nv.nvmlDeviceGetHandleByIndex(i)
                raw=self.nv.nvmlDeviceGetName(h)
                name=raw.decode("utf-8","ignore") if isinstance(raw,(bytes,bytearray)) else str(raw)
            except Exception:
                name=f"NVIDIA GPU {i}"
            out.append(name)
        return out
    
    def gpu_read(self, idx=0):
        if not self.ok or idx>=self.count: return {}
        nv=self.nv; h=nv.nvmlDeviceGetHandleByIndex(idx)
        raw=nv.nvmlDeviceGetName(h)
        name=raw.decode("utf-8","ignore") if isinstance(raw,(bytes,bytearray)) else str(raw)
        util=nv.nvmlDeviceGetUtilizationRates(h).gpu
        temp=nv.nvmlDeviceGetTemperature(h, nv.NVML_TEMPERATURE_GPU)
        clock=nv.nvmlDeviceGetClockInfo(h, nv.NVML_CLOCK_SM)
        mem=nv.nvmlDeviceGetMemoryInfo(h)
        power=None
        try: power=nv.nvmlDeviceGetPowerUsage(h)/1000.0
        except Exception: pass
        return {"name":name,"util":float(util),"temp":float(temp),"clock_mhz":float(clock),
                "mem_used_b":float(mem.used),"mem_total_b":float(mem.total),"power":power}

class SystemInfo:
    def __init__(self): self._w=wmi.WMI() if wmi else None
    
    def cpu_name_wmi(self):
        if not self._w: return None
        try: return self._w.Win32_Processor()[0].Name.strip()
        except Exception: return None
    
    def mem_freq_mhz(self):
        if not self._w: return None
        try:
            sp=[]
            for m in self._w.Win32_PhysicalMemory():
                v=int(m.Speed) if m.Speed is not None else (int(m.ConfiguredClockSpeed) if m.ConfiguredClockSpeed is not None else None)
                if v: sp.append(v)
            return max(sp) if sp else None
        except Exception: return None

class Disks:
    def __init__(self):
        self._w=wmi.WMI() if wmi else None
        self.phys=[]; self._prev={}; self._prev_t=None; self._build()
    
    def _build(self):
        self.phys=[]
        if not self._w: return
        try:
            for d in self._w.Win32_DiskDrive():
                idx=int(d.Index); size=int(d.Size) if d.Size is not None else 0
                model=(d.Model or f"PhysicalDrive{idx}").strip(); letters=[]
                for p in d.associators("Win32_DiskDriveToDiskPartition"):
                    for ld in p.associators("Win32_LogicalDiskToPartition"):
                        if ld.DeviceID: letters.append(ld.DeviceID)
                self.phys.append({"index":idx,"model":model,"size":size,"letters":sorted(set(letters))})
        except Exception: pass
        self.phys.sort(key=lambda x:x["index"])
    
    @staticmethod
    def _devkey(i): return f"PhysicalDrive{i}"
    
    def _io_snapshot(self):
        out={}
        try:
            io=psutil.disk_io_counters(perdisk=True)
            for k,v in io.items(): out[k]=(v.read_bytes,v.write_bytes)
        except Exception: pass
        return out
    
    def read(self):
        now=time.time(); cur=self._io_snapshot(); dt=(now-self._prev_t) if self._prev_t else None
        out=[]
        for d in self.phys:
            used=0
            for L in d["letters"]:
                try: used+=psutil.disk_usage(L+"\\").used
                except Exception: pass
            rps=wps=None; dev=self._devkey(d["index"])
            if dev in cur and dev in self._prev and dt and dt>0:
                rps=max(0,(cur[dev][0]-self._prev[dev][0])/dt)
                wps=max(0,(cur[dev][1]-self._prev[dev][1])/dt)
            out.append({"index":d["index"],"model":d["model"],"size":d["size"],"used":used,"rps":rps,"wps":wps})
        self._prev, self._prev_t = cur, now
        return out

class Network:
    def __init__(self): self._prev=None; self._prev_t=None
    
    def read(self):
        now=time.time(); c=psutil.net_io_counters(pernic=False)
        up=down=None
        if self._prev is not None:
            dt=now-self._prev_t
            if dt>0:
                up=max(0,(c.bytes_sent-self._prev[0])/dt)
                down=max(0,(c.bytes_recv-self._prev[1])/dt)
        self._prev=(c.bytes_sent,c.bytes_recv); self._prev_t=now
        return {"up":up,"down":down}

class HardwareMonitor:
    def __init__(self):
        self.lhm = LHM()
        self.nvml = NVML()
        self.sysi = SystemInfo()
        self.disks = Disks()
        self.network = Network()
        
        self.gpu_names = self._get_gpu_names()
        self.mem_freq_cache = self.sysi.mem_freq_mhz()
        
        self.disks.read()
        self.network.read()
    
    def _get_gpu_names(self):
        names_lhm = self.lhm.list_gpus() if self.lhm.ok else []
        names_nvml = self.nvml.list_gpus() if self.nvml.ok else []
        gpu_names = names_lhm[:] + [n for n in names_nvml if n not in names_lhm]
        if not gpu_names: gpu_names = ["（未检测到 GPU）"]
        return gpu_names
    
    def is_lhm_loaded(self):
        return self.lhm.ok
    
    def get_cpu_name(self):
        return self.lhm.cpu_name() or self.sysi.cpu_name_wmi() or "CPU"
    
    def get_cpu_data(self):
        c = self.lhm.cpu_read() if self.lhm.ok else {}
        if c.get("usage") is None:
            try: c["usage"] = psutil.cpu_percent(interval=None)
            except Exception: pass
        return c
    
    def get_gpu_data(self, gpu_index=0):
        if gpu_index >= len(self.gpu_names):
            return {}
        
        sel_name = self.gpu_names[gpu_index]
        names_lhm = self.lhm.list_gpus() if self.lhm.ok else []
        names_nvml = self.nvml.list_gpus() if self.nvml.ok else []
        
        if sel_name in names_lhm:
            g = self.lhm.gpu_read(gpu_index if gpu_index < len(names_lhm) else 0) if self.lhm.ok else {}
        else:
            idx = [i for i,n in enumerate(names_nvml) if n==sel_name]
            g = self.nvml.gpu_read(idx[0]) if (self.nvml.ok and idx) else {}
        return g
    
    def get_memory_data(self):
        m_lhm = self.lhm.memory_read() if self.lhm.ok else {}
        vm = psutil.virtual_memory()
        used_b  = m_lhm.get("used_b",  vm.total - vm.available)
        total_b = m_lhm.get("total_b", vm.total)
        percent = m_lhm.get("percent", (used_b/total_b)*100.0 if total_b else None)
        
        return {
            "used_b": used_b,
            "total_b": total_b,
            "percent": percent,
            "freq_mhz": self.mem_freq_cache
        }
    
    def get_disk_data(self):
        return self.disks.read()
    
    def get_network_data(self):
        return self.network.read()

def bytes2human(n):
    if n is None: return "—"
    n = float(n); units=("B","KB","MB","GB","TB","PB"); i=0
    while n >= 1024 and i < len(units)-1: n/=1024; i+=1
    return f"{n:.1f} {units[i]}" if i else f"{int(n)} {units[i]}"

def pct_str(v):   return "—" if v is None or (isinstance(v,float) and math.isnan(v)) else f"{v:.0f}%"
def mhz_str(v):  return "—" if v is None or (isinstance(v,float) and math.isnan(v)) else f"{v:.0f} MHz"
def temp_str(v): return "—" if v is None or (isinstance(v,float) and math.isnan(v)) else f"{v:.0f} °C"
def watt_str(v): return "—" if v is None or (isinstance(v,float) and math.isnan(v)) else f"{v:.0f} W"