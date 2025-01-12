"""
utility.py: defines miscellaneous utility services.
"""

import os

from core import CoreCommandError, constants, utils
from core.nodes.ipaddress import Ipv4Prefix, Ipv6Prefix
from core.services.coreservices import CoreService


class UtilService(CoreService):
    """
    Parent class for utility services.
    """

    name = None
    group = "Utility"
    dirs = ()
    configs = ()
    startup = ()
    shutdown = ()

    @classmethod
    def generate_config(cls, node, filename):
        return ""


class IPForwardService(UtilService):
    name = "IPForward"
    configs = ("ipforward.sh",)
    startup = ("sh ipforward.sh",)

    @classmethod
    def generate_config(cls, node, filename):
        if os.uname()[0] == "Linux":
            return cls.generateconfiglinux(node, filename)
        else:
            raise Exception("unknown platform")

    @classmethod
    def generateconfiglinux(cls, node, filename):
        cfg = """\
#!/bin/sh
# auto-generated by IPForward service (utility.py)
%(sysctl)s -w net.ipv4.conf.all.forwarding=1
%(sysctl)s -w net.ipv4.conf.default.forwarding=1
%(sysctl)s -w net.ipv6.conf.all.forwarding=1
%(sysctl)s -w net.ipv6.conf.default.forwarding=1
%(sysctl)s -w net.ipv4.conf.all.send_redirects=0
%(sysctl)s -w net.ipv4.conf.default.send_redirects=0
%(sysctl)s -w net.ipv4.conf.all.rp_filter=0
%(sysctl)s -w net.ipv4.conf.default.rp_filter=0
""" % {
            "sysctl": constants.SYSCTL_BIN
        }
        for ifc in node.netifs():
            name = utils.sysctl_devname(ifc.name)
            cfg += "%s -w net.ipv4.conf.%s.forwarding=1\n" % (
                constants.SYSCTL_BIN,
                name,
            )
            cfg += "%s -w net.ipv4.conf.%s.send_redirects=0\n" % (
                constants.SYSCTL_BIN,
                name,
            )
            cfg += "%s -w net.ipv4.conf.%s.rp_filter=0\n" % (constants.SYSCTL_BIN, name)
        return cfg


class DefaultRouteService(UtilService):
    name = "DefaultRoute"
    configs = ("defaultroute.sh",)
    startup = ("sh defaultroute.sh",)

    @classmethod
    def generate_config(cls, node, filename):
        cfg = "#!/bin/sh\n"
        cfg += "# auto-generated by DefaultRoute service (utility.py)\n"
        for ifc in node.netifs():
            if hasattr(ifc, "control") and ifc.control is True:
                continue
            cfg += "\n".join(map(cls.addrstr, ifc.addrlist))
            cfg += "\n"
        return cfg

    @staticmethod
    def addrstr(x):
        if x.find(":") >= 0:
            net = Ipv6Prefix(x)
        else:
            net = Ipv4Prefix(x)
        if net.max_addr() == net.min_addr():
            return ""
        else:
            if os.uname()[0] == "Linux":
                rtcmd = "ip route add default via"
            else:
                raise Exception("unknown platform")
            return "%s %s" % (rtcmd, net.min_addr())


class DefaultMulticastRouteService(UtilService):
    name = "DefaultMulticastRoute"
    configs = ("defaultmroute.sh",)
    startup = ("sh defaultmroute.sh",)

    @classmethod
    def generate_config(cls, node, filename):
        cfg = "#!/bin/sh\n"
        cfg += "# auto-generated by DefaultMulticastRoute service (utility.py)\n"
        cfg += "# the first interface is chosen below; please change it "
        cfg += "as needed\n"

        for ifc in node.netifs():
            if hasattr(ifc, "control") and ifc.control is True:
                continue
            if os.uname()[0] == "Linux":
                rtcmd = "ip route add 224.0.0.0/4 dev"
            else:
                raise Exception("unknown platform")
            cfg += "%s %s\n" % (rtcmd, ifc.name)
            cfg += "\n"
            break
        return cfg


class StaticRouteService(UtilService):
    name = "StaticRoute"
    configs = ("staticroute.sh",)
    startup = ("sh staticroute.sh",)
    custom_needed = True

    @classmethod
    def generate_config(cls, node, filename):
        cfg = "#!/bin/sh\n"
        cfg += "# auto-generated by StaticRoute service (utility.py)\n#\n"
        cfg += "# NOTE: this service must be customized to be of any use\n"
        cfg += "#       Below are samples that you can uncomment and edit.\n#\n"
        for ifc in node.netifs():
            if hasattr(ifc, "control") and ifc.control is True:
                continue
            cfg += "\n".join(map(cls.routestr, ifc.addrlist))
            cfg += "\n"
        return cfg

    @staticmethod
    def routestr(x):
        if x.find(":") >= 0:
            net = Ipv6Prefix(x)
            dst = "3ffe:4::/64"
        else:
            net = Ipv4Prefix(x)
            dst = "10.9.8.0/24"
        if net.max_addr() == net.min_addr():
            return ""
        else:
            if os.uname()[0] == "Linux":
                rtcmd = "#/sbin/ip route add %s via" % dst
            else:
                raise Exception("unknown platform")
            return "%s %s" % (rtcmd, net.min_addr())


class SshService(UtilService):
    name = "SSH"
    configs = ("startsshd.sh", "/etc/ssh/sshd_config")
    dirs = ("/etc/ssh", "/var/run/sshd")
    startup = ("sh startsshd.sh",)
    shutdown = ("killall sshd",)
    validate = ()

    @classmethod
    def generate_config(cls, node, filename):
        """
        Use a startup script for launching sshd in order to wait for host
        key generation.
        """
        sshcfgdir = cls.dirs[0]
        sshstatedir = cls.dirs[1]
        sshlibdir = "/usr/lib/openssh"
        if filename == "startsshd.sh":
            return """\
#!/bin/sh
# auto-generated by SSH service (utility.py)
ssh-keygen -q -t rsa -N "" -f %s/ssh_host_rsa_key
chmod 655 %s
# wait until RSA host key has been generated to launch sshd
/usr/sbin/sshd -f %s/sshd_config
""" % (
                sshcfgdir,
                sshstatedir,
                sshcfgdir,
            )
        else:
            return """\
# auto-generated by SSH service (utility.py)
Port 22
Protocol 2
HostKey %s/ssh_host_rsa_key
UsePrivilegeSeparation yes
PidFile %s/sshd.pid

KeyRegenerationInterval 3600
ServerKeyBits 768

SyslogFacility AUTH
LogLevel INFO

LoginGraceTime 120
PermitRootLogin yes
StrictModes yes

RSAAuthentication yes
PubkeyAuthentication yes

IgnoreRhosts yes
RhostsRSAAuthentication no
HostbasedAuthentication no

PermitEmptyPasswords no
ChallengeResponseAuthentication no

X11Forwarding yes
X11DisplayOffset 10
PrintMotd no
PrintLastLog yes
TCPKeepAlive yes

AcceptEnv LANG LC_*
Subsystem sftp %s/sftp-server
UsePAM yes
UseDNS no
""" % (
                sshcfgdir,
                sshstatedir,
                sshlibdir,
            )


class DhcpService(UtilService):
    name = "DHCP"
    configs = ("/etc/dhcp/dhcpd.conf",)
    dirs = ("/etc/dhcp", "/var/lib/dhcp")
    startup = ("touch /var/lib/dhcp/dhcpd.leases", "dhcpd")
    shutdown = ("killall dhcpd",)
    validate = ("pidof dhcpd",)

    @classmethod
    def generate_config(cls, node, filename):
        """
        Generate a dhcpd config file using the network address of
        each interface.
        """
        cfg = """\
# auto-generated by DHCP service (utility.py)
# NOTE: move these option lines into the desired pool { } block(s) below
#option domain-name "test.com";
#option domain-name-servers 10.0.0.1;
#option routers 10.0.0.1;

log-facility local6;

default-lease-time 600;
max-lease-time 7200;

ddns-update-style none;
"""
        for ifc in node.netifs():
            if hasattr(ifc, "control") and ifc.control is True:
                continue
            cfg += "\n".join(map(cls.subnetentry, ifc.addrlist))
            cfg += "\n"
        return cfg

    @staticmethod
    def subnetentry(x):
        """
        Generate a subnet declaration block given an IPv4 prefix string
        for inclusion in the dhcpd3 config file.
        """
        if x.find(":") >= 0:
            return ""
        else:
            addr = x.split("/")[0]
            net = Ipv4Prefix(x)
            # divide the address space in half
            rangelow = net.addr(net.num_addr() / 2)
            rangehigh = net.max_addr()
            return """
subnet %s netmask %s {
  pool {
    range %s %s;
    default-lease-time 600;
    option routers %s;
  }
}
""" % (
                net.prefix_str(),
                net.netmask_str(),
                rangelow,
                rangehigh,
                addr,
            )


class DhcpClientService(UtilService):
    """
    Use a DHCP client for all interfaces for addressing.
    """

    name = "DHCPClient"
    configs = ("startdhcpclient.sh",)
    startup = ("sh startdhcpclient.sh",)
    shutdown = ("killall dhclient",)
    validate = ("pidof dhclient",)

    @classmethod
    def generate_config(cls, node, filename):
        """
        Generate a script to invoke dhclient on all interfaces.
        """
        cfg = "#!/bin/sh\n"
        cfg += "# auto-generated by DHCPClient service (utility.py)\n"
        cfg += "# uncomment this mkdir line and symlink line to enable client-"
        cfg += "side DNS\n# resolution based on the DHCP server response.\n"
        cfg += "#mkdir -p /var/run/resolvconf/interface\n"

        for ifc in node.netifs():
            if hasattr(ifc, "control") and ifc.control is True:
                continue
            cfg += "#ln -s /var/run/resolvconf/interface/%s.dhclient" % ifc.name
            cfg += " /var/run/resolvconf/resolv.conf\n"
            cfg += "/sbin/dhclient -nw -pf /var/run/dhclient-%s.pid" % ifc.name
            cfg += " -lf /var/run/dhclient-%s.lease %s\n" % (ifc.name, ifc.name)
        return cfg


class FtpService(UtilService):
    """
    Start a vsftpd server.
    """

    name = "FTP"
    configs = ("vsftpd.conf",)
    dirs = ("/var/run/vsftpd/empty", "/var/ftp")
    startup = ("vsftpd ./vsftpd.conf",)
    shutdown = ("killall vsftpd",)
    validate = ("pidof vsftpd",)

    @classmethod
    def generate_config(cls, node, filename):
        """
        Generate a vsftpd.conf configuration file.
        """
        return """\
# vsftpd.conf auto-generated by FTP service (utility.py)
listen=YES
anonymous_enable=YES
local_enable=YES
dirmessage_enable=YES
use_localtime=YES
xferlog_enable=YES
connect_from_port_20=YES
xferlog_file=/var/log/vsftpd.log
ftpd_banner=Welcome to the CORE FTP service
secure_chroot_dir=/var/run/vsftpd/empty
anon_root=/var/ftp
"""


class HttpService(UtilService):
    """
    Start an apache server.
    """

    name = "HTTP"
    configs = (
        "/etc/apache2/apache2.conf",
        "/etc/apache2/envvars",
        "/var/www/index.html",
    )
    dirs = (
        "/etc/apache2",
        "/var/run/apache2",
        "/var/log/apache2",
        "/run/lock",
        "/var/lock/apache2",
        "/var/www",
    )
    startup = ("chown www-data /var/lock/apache2", "apache2ctl start")
    shutdown = ("apache2ctl stop",)
    validate = ("pidof apache2",)

    APACHEVER22, APACHEVER24 = (22, 24)

    @classmethod
    def generate_config(cls, node, filename):
        """
        Generate an apache2.conf configuration file.
        """
        if filename == cls.configs[0]:
            return cls.generateapache2conf(node, filename)
        elif filename == cls.configs[1]:
            return cls.generateenvvars(node, filename)
        elif filename == cls.configs[2]:
            return cls.generatehtml(node, filename)
        else:
            return ""

    @classmethod
    def detectversionfromcmd(cls):
        """
        Detect the apache2 version using the 'a2query' command.
        """
        try:
            status, result = utils.cmd_output(["a2query", "-v"])
        except CoreCommandError:
            status = -1

        if status == 0 and result[:3] == "2.4":
            return cls.APACHEVER24

        return cls.APACHEVER22

    @classmethod
    def generateapache2conf(cls, node, filename):
        lockstr = {
            cls.APACHEVER22: "LockFile ${APACHE_LOCK_DIR}/accept.lock\n",
            cls.APACHEVER24: "Mutex file:${APACHE_LOCK_DIR} default\n",
        }
        mpmstr = {
            cls.APACHEVER22: "",
            cls.APACHEVER24: "LoadModule mpm_worker_module /usr/lib/apache2/modules/mod_mpm_worker.so\n",
        }

        permstr = {
            cls.APACHEVER22: "    Order allow,deny\n    Deny from all\n    Satisfy all\n",
            cls.APACHEVER24: "    Require all denied\n",
        }

        authstr = {
            cls.APACHEVER22: "LoadModule authz_default_module /usr/lib/apache2/modules/mod_authz_default.so\n",
            cls.APACHEVER24: "LoadModule authz_core_module /usr/lib/apache2/modules/mod_authz_core.so\n",
        }

        permstr2 = {
            cls.APACHEVER22: "\t\tOrder allow,deny\n\t\tallow from all\n",
            cls.APACHEVER24: "\t\tRequire all granted\n",
        }

        version = cls.detectversionfromcmd()
        cfg = "# apache2.conf generated by utility.py:HttpService\n"
        cfg += lockstr[version]
        cfg += """\
PidFile ${APACHE_PID_FILE}
Timeout 300
KeepAlive On
MaxKeepAliveRequests 100
KeepAliveTimeout 5
"""
        cfg += mpmstr[version]
        cfg += """\

<IfModule mpm_prefork_module>
    StartServers          5
    MinSpareServers       5
    MaxSpareServers      10
    MaxClients          150
    MaxRequestsPerChild   0
</IfModule>

<IfModule mpm_worker_module>
    StartServers          2
    MinSpareThreads      25
    MaxSpareThreads      75
    ThreadLimit          64
    ThreadsPerChild      25
    MaxClients          150
    MaxRequestsPerChild   0
</IfModule>

<IfModule mpm_event_module>
    StartServers          2
    MinSpareThreads      25
    MaxSpareThreads      75
    ThreadLimit          64
    ThreadsPerChild      25
    MaxClients          150
    MaxRequestsPerChild   0
</IfModule>

User ${APACHE_RUN_USER}
Group ${APACHE_RUN_GROUP}

AccessFileName .htaccess

<Files ~ "^\\.ht">
"""
        cfg += permstr[version]
        cfg += """\
</Files>

DefaultType None

HostnameLookups Off

ErrorLog ${APACHE_LOG_DIR}/error.log
LogLevel warn

#Include mods-enabled/*.load
#Include mods-enabled/*.conf
LoadModule alias_module /usr/lib/apache2/modules/mod_alias.so
LoadModule auth_basic_module /usr/lib/apache2/modules/mod_auth_basic.so
"""
        cfg += authstr[version]
        cfg += """\
LoadModule authz_host_module /usr/lib/apache2/modules/mod_authz_host.so
LoadModule authz_user_module /usr/lib/apache2/modules/mod_authz_user.so
LoadModule autoindex_module /usr/lib/apache2/modules/mod_autoindex.so
LoadModule dir_module /usr/lib/apache2/modules/mod_dir.so
LoadModule env_module /usr/lib/apache2/modules/mod_env.so

NameVirtualHost *:80
Listen 80

<IfModule mod_ssl.c>
    Listen 443
</IfModule>
<IfModule mod_gnutls.c>
    Listen 443
</IfModule>

LogFormat "%v:%p %h %l %u %t \\"%r\\" %>s %O \\"%{Referer}i\\" \\"%{User-Agent}i\\"" vhost_combined
LogFormat "%h %l %u %t \\"%r\\" %>s %O \\"%{Referer}i\\" \\"%{User-Agent}i\\"" combined
LogFormat "%h %l %u %t \\"%r\\" %>s %O" common
LogFormat "%{Referer}i -> %U" referer
LogFormat "%{User-agent}i" agent

ServerTokens OS
ServerSignature On
TraceEnable Off

<VirtualHost *:80>
    ServerAdmin webmaster@localhost
    DocumentRoot /var/www
    <Directory />
        Options FollowSymLinks
        AllowOverride None
    </Directory>
    <Directory /var/www/>
        Options Indexes FollowSymLinks MultiViews
        AllowOverride None
"""
        cfg += permstr2[version]
        cfg += """\
    </Directory>
    ErrorLog ${APACHE_LOG_DIR}/error.log
    LogLevel warn
    CustomLog ${APACHE_LOG_DIR}/access.log combined
</VirtualHost>

"""
        return cfg

    @classmethod
    def generateenvvars(cls, node, filename):
        return """\
# this file is used by apache2ctl - generated by utility.py:HttpService
# these settings come from a default Ubuntu apache2 installation
export APACHE_RUN_USER=www-data
export APACHE_RUN_GROUP=www-data
export APACHE_PID_FILE=/var/run/apache2.pid
export APACHE_RUN_DIR=/var/run/apache2
export APACHE_LOCK_DIR=/var/lock/apache2
export APACHE_LOG_DIR=/var/log/apache2
export LANG=C
export LANG
"""

    @classmethod
    def generatehtml(cls, node, filename):
        body = (
            """\
<!-- generated by utility.py:HttpService -->
<h1>%s web server</h1>
<p>This is the default web page for this server.</p>
<p>The web server software is running but no content has been added, yet.</p>
"""
            % node.name
        )
        for ifc in node.netifs():
            if hasattr(ifc, "control") and ifc.control is True:
                continue
            body += "<li>%s - %s</li>\n" % (ifc.name, ifc.addrlist)
        return "<html><body>%s</body></html>" % body


class PcapService(UtilService):
    """
    Pcap service for logging packets.
    """

    name = "pcap"
    configs = ("pcap.sh",)
    dirs = ()
    startup = ("sh pcap.sh start",)
    shutdown = ("sh pcap.sh stop",)
    validate = ("pidof tcpdump",)
    meta = "logs network traffic to pcap packet capture files"

    @classmethod
    def generate_config(cls, node, filename):
        """
        Generate a startpcap.sh traffic logging script.
        """
        cfg = """
#!/bin/sh
# set tcpdump options here (see 'man tcpdump' for help)
# (-s snap length, -C limit pcap file length, -n disable name resolution)
DUMPOPTS="-s 12288 -C 10 -n"

if [ "x$1" = "xstart" ]; then

"""
        for ifc in node.netifs():
            if hasattr(ifc, "control") and ifc.control is True:
                cfg += "# "
            redir = "< /dev/null"
            cfg += "tcpdump ${DUMPOPTS} -w %s.%s.pcap -i %s %s &\n" % (
                node.name,
                ifc.name,
                ifc.name,
                redir,
            )
        cfg += """

elif [ "x$1" = "xstop" ]; then
    mkdir -p ${SESSION_DIR}/pcap
    mv *.pcap ${SESSION_DIR}/pcap
fi;
"""
        return cfg


class RadvdService(UtilService):
    name = "radvd"
    configs = ("/etc/radvd/radvd.conf",)
    dirs = ("/etc/radvd",)
    startup = ("radvd -C /etc/radvd/radvd.conf -m logfile -l /var/log/radvd.log",)
    shutdown = ("pkill radvd",)
    validate = ("pidof radvd",)

    @classmethod
    def generate_config(cls, node, filename):
        """
        Generate a RADVD router advertisement daemon config file
        using the network address of each interface.
        """
        cfg = "# auto-generated by RADVD service (utility.py)\n"
        for ifc in node.netifs():
            if hasattr(ifc, "control") and ifc.control is True:
                continue
            prefixes = map(cls.subnetentry, ifc.addrlist)
            if len(prefixes) < 1:
                continue
            cfg += (
                """\
interface %s
{
        AdvSendAdvert on;
        MinRtrAdvInterval 3;
        MaxRtrAdvInterval 10;
        AdvDefaultPreference low;
        AdvHomeAgentFlag off;
"""
                % ifc.name
            )
            for prefix in prefixes:
                if prefix == "":
                    continue
                cfg += (
                    """\
        prefix %s
        {
                AdvOnLink on;
                AdvAutonomous on;
                AdvRouterAddr on;
        };
"""
                    % prefix
                )
            cfg += "};\n"
        return cfg

    @staticmethod
    def subnetentry(x):
        """
        Generate a subnet declaration block given an IPv6 prefix string
        for inclusion in the RADVD config file.
        """
        if x.find(":") >= 0:
            net = Ipv6Prefix(x)
            return str(net)
        else:
            return ""


class AtdService(UtilService):
    """
    Atd service for scheduling at jobs
    """

    name = "atd"
    configs = ("startatd.sh",)
    dirs = ("/var/spool/cron/atjobs", "/var/spool/cron/atspool")
    startup = ("sh startatd.sh",)
    shutdown = ("pkill atd",)

    @classmethod
    def generate_config(cls, node, filename):
        return """
#!/bin/sh
echo 00001 > /var/spool/cron/atjobs/.SEQ
chown -R daemon /var/spool/cron/*
chmod -R 700 /var/spool/cron/*
atd
"""


class UserDefinedService(UtilService):
    """
    Dummy service allowing customization of anything.
    """

    name = "UserDefined"
    meta = "Customize this service to do anything upon startup."
