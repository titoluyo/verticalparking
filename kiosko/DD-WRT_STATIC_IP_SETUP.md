# DD-WRT Static IP Configuration Guide

This guide explains how to configure a static IP address for your Raspberry Pi (or any device) based on its MAC address in DD-WRT.

## Overview

DD-WRT supports **DHCP Reservations** (also called Static DHCP Leases), which assign a fixed IP address to a device based on its MAC address. This is better than configuring static IPs on the device itself because:

- Centralized management (all IPs configured in one place)
- Works with DHCP (device still gets DNS, gateway, etc. automatically)
- Prevents IP conflicts
- Easy to change IPs without accessing each device

## Step 1: Get Your Raspberry Pi's MAC Address

On your Raspberry Pi, run:

```bash
# Get MAC address for the active network interface (usually eth0 or wlan0)
ip link show | grep -A 1 "state UP" | grep -oP '(?<=link/ether )[^ ]+'

# Or for a specific interface:
ip link show eth0 | grep -oP '(?<=link/ether )[^ ]+'
ip link show wlan0 | grep -oP '(?<=link/ether )[^ ]+'

# Alternative method:
cat /sys/class/net/eth0/address
cat /sys/class/net/wlan0/address
```

**Note:** The MAC address format should be: `XX:XX:XX:XX:XX:XX` (with colons) or `XX-XX-XX-XX-XX-XX` (with dashes). DD-WRT accepts both formats.

You can also use the helper script:
```bash
bash kiosko/get_mac_address.sh
```

## Step 2: Access DD-WRT Web Interface

1. Open your web browser
2. Navigate to your router's IP address (usually `192.168.1.1` or `192.168.0.1`)
3. Log in with your DD-WRT admin credentials

## Step 3: Configure Static DHCP Lease

The exact menu location varies by DD-WRT version, but typically:

### Method 1: Services → DHCP Server (Most Common)

1. Go to **Services** → **DHCP Server** (or **Services** → **Services** → **DHCP Server**)
2. Scroll down to **Static Leases** section
3. Click **Add** or the **+** button
4. Fill in the fields:
   - **Hostname**: `control` (or your desired name)
   - **MAC Address**: Enter your Raspberry Pi's MAC address (e.g., `b8:27:eb:12:34:56`)
   - **IP Address**: Enter the desired static IP (e.g., `192.168.1.100`)
     - **Important:** Make sure this IP is outside your DHCP pool range to avoid conflicts
5. Click **Save** or **Apply Settings**

### Method 2: Setup → Basic Setup → Network Setup

Some DD-WRT versions have it under:
1. **Setup** → **Basic Setup**
2. Scroll to **Network Address Server Settings (DHCP)**
3. Look for **Static Leases** section
4. Follow the same steps as Method 1

### Method 3: Advanced → DHCP

1. Go to **Advanced** → **DHCP**
2. Find **Static Leases** section
3. Add entry as described above

## Step 4: Verify DHCP Pool Range

**Important:** Make sure your static IP is **outside** the DHCP pool range.

1. Go to **Setup** → **Basic Setup** → **Network Address Server Settings (DHCP)**
2. Check the **DHCP Server** settings:
   - **DHCP Type**: Should be "Server"
   - **DHCP Start**: e.g., `192.168.1.100`
   - **DHCP Max Users**: e.g., `50`
   - This means DHCP will assign IPs from `192.168.1.100` to `192.168.1.149`

3. **Choose a static IP outside this range**, for example:
   - If DHCP pool is `192.168.1.100-149`, use `192.168.1.50` or `192.168.1.200`
   - Common choices: `192.168.1.10`, `192.168.1.20`, `192.168.1.100` (if pool starts at 101+)

## Step 5: Apply and Reboot

1. Click **Save** or **Apply Settings** at the bottom of the page
2. Wait for the router to apply changes (may take 30-60 seconds)
3. Optionally reboot the router: **Administration** → **Reboot Router**

## Step 6: Renew DHCP Lease on Raspberry Pi

On your Raspberry Pi, renew the DHCP lease to get the new static IP:

```bash
# For wired connection (eth0)
sudo dhclient -r eth0
sudo dhclient eth0

# For wireless connection (wlan0)
sudo dhclient -r wlan0
sudo dhclient wlan0

# Or restart networking
sudo systemctl restart networking

# Or reboot
sudo reboot
```

After renewal, verify the IP:
```bash
ip addr show eth0
# or
hostname -I
```

## Verification

1. **Check IP on Raspberry Pi:**
   ```bash
   ip addr show eth0 | grep "inet "
   ```

2. **Ping from another device:**
   ```bash
   ping 192.168.1.100  # Use your assigned static IP
   ping control.local   # Should also work if mDNS is configured
   ```

3. **Check router's DHCP table:**
   - In DD-WRT, go to **Status** → **LAN** or **Status** → **DHCP Clients**
   - You should see your Raspberry Pi listed with the static IP

## Troubleshooting

### IP Not Changing

- **Release and renew DHCP lease** (see Step 6)
- **Reboot the Raspberry Pi**
- **Check MAC address format** - ensure it matches exactly (colons or dashes)
- **Verify static lease is saved** - check the Static Leases list in DD-WRT

### IP Conflict

- **Check DHCP pool range** - ensure static IP is outside the pool
- **Check for other static leases** - make sure no other device has the same IP
- **Ping the IP** - if something responds, there's a conflict

### Can't Find Static Leases Menu

- **Check DD-WRT version** - older versions may have different menu structure
- **Look for "DHCP Reservations"** or **"Static DHCP"** instead of "Static Leases"
- **Check Advanced menu** - some versions hide it under Advanced settings

## Example Configuration

For a typical home network setup:

- **Router IP**: `192.168.1.1`
- **DHCP Pool**: `192.168.1.100` - `192.168.1.199` (100 addresses)
- **Static IP for Raspberry Pi**: `192.168.1.10`
- **MAC Address**: `b8:27:eb:12:34:56` (example)
- **Hostname**: `control`

This ensures:
- Router and static devices use low IPs (1-99)
- DHCP clients use middle range (100-199)
- No conflicts between static and dynamic IPs

## Benefits of This Approach

1. **Combined with mDNS**: Your Pi will be accessible as both:
   - `control.local` (via mDNS)
   - `192.168.1.10` (via static IP)

2. **Reliable**: Static IP ensures the Pi always has the same address, even if mDNS fails

3. **Network Management**: Easy to see which devices have static IPs in the router interface

4. **Port Forwarding**: If you need to forward ports, static IPs make it easier

## Related Files

- `kiosko/setup_hostname.sh` - Sets up mDNS hostname (`control.local`)
- `kiosko/get_mac_address.sh` - Helper script to get MAC address

