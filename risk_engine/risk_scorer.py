import re

# High-risk system core packages
CRITICAL_PACKAGES = {
    "linux-image": "Kernel update",
    "linux-headers": "Kernel header update",
    "systemd": "Init system update",
    "libc6": "C standard library update",
    "grub": "Bootloader update",
    "xorg": "Display server update",
    "wayland": "Display server update",
    "dbus": "System bus update"
}

# Driver package to loaded kernel module mappings
DRIVER_MODULE_MAP = {
    "nvidia": ["nvidia", "nvidia_uvm", "nvidia_drm", "nvidia_modeset"],
    "wireguard": ["wireguard"],
    "virtualbox": ["vboxdrv", "vboxnetflt"],
    "docker": ["overlay", "br_netfilter"]
}

def parse_major_version(ver_str):
    """Extracts the leading numerical major version."""
    match = re.search(r'(\d+)', str(ver_str))
    return int(match.group(1)) if match else None

def score_all_updates(pending_updates, loaded_modules=None, hardware=None):
    """
    Evaluates risk based on package criticality, active loaded modules, 
    and version shift magnitude.
    """
    loaded_modules = loaded_modules or []
    scored = []

    for pkg in pending_updates:
        item = dict(pkg)
        name = item.get("package", "").lower()
        old_ver = item.get("old_version", "")
        new_ver = item.get("new_version", "")
        
        score = 0
        signals = []

        # Signal 1: Core System Component Check
        for crit_pkg, label in CRITICAL_PACKAGES.items():
            if crit_pkg in name:
                score += 45
                signals.append(f"Critical System Infrastructure: {label}")
                break

        # Signal 2: Loaded Kernel Module Conflict Check
        for driver_key, modules in DRIVER_MODULE_MAP.items():
            if driver_key in name:
                # Check if any associated driver module is currently running in kernel space
                active_conflicts = [m for m in modules if m in loaded_modules]
                if active_conflicts:
                    score += 40
                    signals.append(f"Modifies active kernel modules running in RAM: ({', '.join(active_conflicts)})")
                else:
                    score += 20
                    signals.append(f"Driver package update detected ({driver_key})")

        # Signal 3: Major Version Jump Check
        old_major = parse_major_version(old_ver)
        new_major = parse_major_version(new_ver)
        if old_major and new_major and (new_major > old_major):
            score += 25
            signals.append(f"Major version bump detected ({old_major}.x -> {new_major}.x)")

        # Fallback for standard packages
        if score == 0:
            score = 10
            signals.append("Standard user-space package update")

        # Cap score at 100
        score = min(score, 100)

        # Assign Risk Severity Levels
        if score >= 70:
            level = "HIGH"
        elif score >= 40:
            level = "MEDIUM"
        else:
            level = "LOW"

        item["score"] = score
        item["level"] = level
        item["signals"] = signals
        scored.append(item)

    return scored
