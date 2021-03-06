__author__ = 'ryanvade'
from Tkinter import *
import tkMessageBox
import uuid
import os
import shutil
import hashlib
import fcntl
import socket
import struct

import dbus


# The Following function is from http://bit.ly/1ceqal5
def getHwAddr(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', ifname[:15]))
    return ':'.join(['%02x' % ord(char) for char in info[18:24]])


def getWifiDeviceMAC(bus):
    # possible device types
    devtypes = {1: "Ethernet",
                2: "Wi-Fi",
                5: "Bluetooth",
                6: "OLPC",
                7: "WiMAX",
                8: "Modem",
                9: "InfiniBand",
                10: "Bond",
                11: "VLAN",
                12: "ADSL",
                13: "Bridge",
                14: "Generic",
                15: "Team"
                }
    service_name = "org.freedesktop.NetworkManager"
    # custom proxy just for interfacing with devices
    device_proxy = bus.get_object(service_name, "/org/freedesktop/NetworkManager")
    manager = dbus.Interface(device_proxy, service_name)
    # get all of the device objects on the system
    devices = manager.GetDevices()
    # empty string
    wanted_device_name = ""
    wanted_mac = ""

    for d in devices:
        # device object proxy
        dev_proxy = bus.get_object(service_name, d)
        # device properties interface
        dev_prop_iface = dbus.Interface(dev_proxy, "org.freedesktop.DBus.Properties")
        # devices properties
        props = dev_prop_iface.GetAll(service_name + ".Device")

        # what if the device type is not known ?
        try:
            devtype = devtypes[props['DeviceType']]
        except KeyError:
            devtype = "Unknown"
        # right now we are only getting the first wifi device. Multiple WIFI devices could cause issues
        # TODO only use active or unactive wifi connections
        if devtype == "Wi-Fi":
            wanted_device_name = props['Interface']
            break
            # no empty strings please
    if not wanted_device_name == "":
        # we have to typecast dbus.string to standard string
        wanted_mac = getHwAddr(str(wanted_device_name))
    return wanted_mac


def getFileMD5SUM(filename, blocksize=2 * 20):
    md5Object = hashlib.md5()
    # open the file for reading
    with open(filename, 'r') as f:
        while True:
            # add file contents to buffer in blocksize chunks
            buffer = f.read(blocksize)
            # when the buffer is empty
            if not buffer:
                break
            # add buffer to md5sum object
            md5Object.update(buffer)
    f.close()
    # hexidigest is a string with the md5sum in hex format
    return md5Object.hexdigest()


def security_error_window(message):
    tkMessageBox.showerror(title="Certificate Error", message=message)
    # we also stop the program...
    # TODO clean up if needed..
    return



def isSumCorrect(file, properHash):
    # don't assume file exists...
    if os.path.isfile(file):
        # TODO don't use insecure MD5 but rather sha256 or sha512
        sum = getFileMD5SUM(file)
        if properHash == sum:
            return True
        else:
            security_error_window("Error: Certificate does not pass security check.")
            sys.exit(1)
    else:
        security_error_window("Error: Certificate is missing. There may be an issue with your download.")
        sys.exit(1)


def setup_Certificate(cert_location, cert_name):
    # Check if the directory for the certificate exists, if not make it
    if not os.path.exists(cert_location):
        os.mkdir(cert_location)
    # If the certificate exists alreay, remove it to keep things pure.
    if os.path.isfile(cert_location + cert_name):
        os.remove(cert_location + cert_name)
    # get the current working directory
    work_dir = os.getcwd() + "/"
    # check the files sha256 sum
    # TODO get hash from file for better security IE from ITS directly via .md5sum file or .sha*sum file
    properHash = "1663fb443486f27ae568b9da1eaf1a0a"
    if isSumCorrect(work_dir + cert_name, properHash):
        shutil.copy2(work_dir + cert_name, cert_location)


def path_dbusByteArray(path):
    # Generate a Dbuse ByteArray to be used with ca-cert
    return dbus.ByteArray("file://" + path + "\0")


def WPASETUP():
    user_home = os.getenv("HOME")
    cert_location = user_home + '/.config/SIUE_WPA/'
    cert_name = "oitca.cer"
    cert = cert_location + cert_name
    UUID = str(uuid.uuid4())

    setup_Certificate(cert_location, cert_name)

    bus = dbus.SystemBus()  # dbus connection

    eid = entryWidget.get()
    MAC = str(getWifiDeviceMAC(bus))
    # TODO mac address of wireless device? Is it really needed? Why is it not being set?
    s_con = dbus.Dictionary({
        'type': '802-11-wireless',
        'uuid': UUID,
        'id': 'SIUE-WPA',
        'mac-address': dbus.ByteArray(MAC)})

    s_wifi = dbus.Dictionary({
        'ssid': dbus.ByteArray("SIUE-WPA"),
        'mode': 'infrastructure',
        'security': '802-11-wireless-security'})

    s_wsec = dbus.Dictionary({
        'key-mgmt': 'wpa-eap'})

    s_8021x = dbus.Dictionary({
        'eap': ['peap'],
        'identity': eid,
        'ca-cert': path_dbusByteArray(cert),
        'system-ca-certs': True,
        'password-flags': dbus.UInt32(1),
        'phase2-auth': 'mschapv2'})

    s_ip4 = dbus.Dictionary({'method': 'auto'})
    s_ip6 = dbus.Dictionary({'method': 'ignore'})

    con = dbus.Dictionary({
        'connection': s_con,
        '802-11-wireless': s_wifi,
        '802-11-wireless-security': s_wsec,
        '802-1x': s_8021x,
        'ipv4': s_ip4,
        'ipv6': s_ip6
    })
    service_name = "org.freedesktop.NetworkManager"  # what service in dbus are we using
    proxy = bus.get_object(service_name, "/org/freedesktop/NetworkManager/Settings")  # dbus nm settings object
    settings = dbus.Interface(proxy, "org.freedesktop.NetworkManager.Settings")  # interface for the object

    settings.AddConnection(con)  # Finally, the SIUE-WPA NM profile
    tkMessageBox.showinfo(title="Done", message="WPA Setup is Complete")
    root.destroy()  # program is done. Exit.


def on_continue_button():
    global entryWidget

    if entryWidget.get().strip() == "":
        tkMessageBox.showerror("Error", "Please enter your EID.")
    else:
        WPASETUP()

if __name__ == "__main__":
    root = Tk()

    root.title("UNOFFICIAL SIUE WPA SETUP TOOL FOR LINUX")
    root["padx"] = 40
    root["pady"] = 20

    # Create a text frame to hold the text Label and the Entry widget
    textFrame = Frame(root)

    # Create a Label to say what the program does
    welcomeLabel = Label(textFrame)
    welcomeLabel["text"] = "Welcome to the (Unofficial) SIUE WPA setup tool for Linux!"
    welcomeLabel.pack(side=TOP)

    # Create a Label in textFrame
    entryLabel = Label(textFrame)
    entryLabel["text"] = "Enter your eid:"
    entryLabel.pack(side=LEFT)

    # Create an Entry Widget in textFrame
    entryWidget = Entry(textFrame)
    entryWidget["width"] = 50
    entryWidget.pack(side=LEFT)

    textFrame.pack()

    button = Button(root, text="Submit", command=on_continue_button)
    button.pack()

    root.mainloop()
