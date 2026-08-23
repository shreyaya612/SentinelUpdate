import subprocess
import re
import os
import sys

def get_system_context():
    """Gathers critical system state (kernel, modules, hardware) to feed the risk scorer & LLM."""
    context = {
        "kernel": "Unknown",
        "loaded_modules": [],
        "hardware": []
    }
    
    # 1. Kernel Version
    try:
        context["kernel"] = subprocess.check_output(['uname', '-r'], text=True).strip()
    except Exception:
        context["kernel"] = "Non-Linux Environment"

    # 2. Loaded Kernel Modules (lsmod)
    try:
        lsmod_out = subprocess.check_output(['lsmod'], text=True).strip().split('\n')
        # Skip header and extract first column (module name)
        modules = [line.split()[0] for line in lsmod_out[1:] if line.strip()]
        context["loaded_modules"] = modules
    except Exception:
        context["loaded_modules"] = []

    # 3. Critical Hardware (lspci)
    try:
        lspci_out = subprocess.check_output(['lspci'], text=True).strip().split('\n')
        keywords = ['VGA', '3D', 'Network', 'Audio', 'Ethernet', 'NVIDIA', 'AMD']
        context["hardware"] = [line for line in lspci_out if any(k in line for k in keywords)]
    except Exception:
        context["hardware"] = []

    return context

def get_loaded_modules():
    """Helper function to fetch currently loaded kernel modules."""
    return get_system_context().get("loaded_modules", [])

def get_pending_updates():
    """
    Simulates an apt upgrade using `apt-get -s upgrade` and parses pending changes.
    Does NOT require root/sudo access because -s runs in simulation mode.
    """
    # Force English output so regex matches 'Inst' reliably regardless of system locale
    env = os.environ.copy()
    env["LC_ALL"] = "C"

    try:
        result = subprocess.run(
            ['apt-get', '-s', 'upgrade'],
            capture_output=True,
            text=True,
            env=env
        )
    except Exception:
        # Running on non-Debian/Ubuntu/Linux platform
        return []

    updates = []
    
    # Matches apt simulation lines like:
    # Inst linux-image-6.8.0-49-generic [6.8.0-48.48] (6.8.0-49.49 Ubuntu:24.04/noble [amd64])
    pattern = re.compile(r'^Inst\s+(\S+)\s+\[([^\]]+)\]\s+\((([^\s\)]+).*)\)', re.MULTILINE)
    
    for match in pattern.finditer(result.stdout):
        updates.append({
            "package": match.group(1),
            "old_version": match.group(2),
            "new_version": match.group(4)
        })
        
    return updates

def scan_system():
    """Main scanner entry point called by main.py."""
    context = get_system_context()
    updates = get_pending_updates()
    
    return {
        "system_context": context,
        "pending_updates": updates
    }
