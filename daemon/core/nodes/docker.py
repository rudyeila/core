import json
import logging
import os

from core import CoreCommandError, utils
from core.emulator.enumerations import NodeTypes
from core.nodes.base import CoreNode


class DockerClient(object):
    def __init__(self, name, image):
        self.name = name
        self.image = image
        self.pid = None
        self._addr = {}

    def create_container(self):
        utils.check_cmd(
            "docker run -td --init --net=none --hostname {name} --name {name} "
            "--sysctl net.ipv6.conf.all.disable_ipv6=0 "
            "{image} /bin/bash".format(
                name=self.name,
                image=self.image
            ))
        self.pid = self.get_pid()
        return self.pid

    def get_info(self):
        args = "docker inspect {name}".format(name=self.name)
        status, output = utils.cmd_output(args)
        if status:
            raise CoreCommandError(status, args, output)
        data = json.loads(output)
        if not data:
            raise CoreCommandError(status, args, "docker({name}) not present".format(name=self.name))
        return data[0]

    def is_alive(self):
        try:
            data = self.get_info()
            return data["State"]["Running"]
        except CoreCommandError:
            return False

    def stop_container(self):
        utils.check_cmd("docker rm -f {name}".format(
            name=self.name
        ))

    def cmd(self, cmd, wait=True):
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        logging.info("docker cmd wait(%s): %s", wait, cmd)
        return utils.cmd("docker exec {name} {cmd}".format(
            name=self.name,
            cmd=cmd
        ), wait)

    def cmd_output(self, cmd):
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        logging.info("docker cmd output: %s", cmd)
        return utils.cmd_output("docker exec {name} {cmd}".format(
            name=self.name,
            cmd=cmd
        ))

    def ns_cmd(self, cmd):
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        args = "nsenter -t {pid} -u -i -p -n {cmd}".format(
            pid=self.pid,
            cmd=cmd
        )
        logging.info("ns cmd: %s", args)
        return utils.cmd_output(args)

    def get_pid(self):
        args = "docker inspect -f '{{{{.State.Pid}}}}' {name}".format(name=self.name)
        status, output = utils.cmd_output(args)
        if status:
            raise CoreCommandError(status, args, output)
        self.pid = output
        logging.debug("node(%s) pid: %s", self.name, self.pid)
        return output

    def copy_file(self, source, destination):
        args = "docker cp {source} {name}:{destination}".format(
            source=source,
            name=self.name,
            destination=destination
        )
        status, output = utils.cmd_output(args)
        if status:
            raise CoreCommandError(status, args, output)

    def getaddr(self, ifname, rescan=False):
        """
        Get address for interface on node.

        :param str ifname: interface name to get address for
        :param bool rescan: rescan flag
        :return: interface information
        :rtype: dict
        """
        if ifname in self._addr and not rescan:
            return self._addr[ifname]

        interface = {"ether": [], "inet": [], "inet6": [], "inet6link": []}
        args = ["ip", "addr", "show", "dev", ifname]
        status, output = self.ns_cmd(args)
        for line in output:
            line = line.strip().split()
            if line[0] == "link/ether":
                interface["ether"].append(line[1])
            elif line[0] == "inet":
                interface["inet"].append(line[1])
            elif line[0] == "inet6":
                if line[3] == "global":
                    interface["inet6"].append(line[1])
                elif line[3] == "link":
                    interface["inet6link"].append(line[1])
                else:
                    logging.warning("unknown scope: %s" % line[3])

        if status:
            logging.warning("nonzero exist status (%s) for cmd: %s", status, args)
        self._addr[ifname] = interface
        return interface


class DockerNode(CoreNode):
    apitype = NodeTypes.DOCKER.value

    def __init__(self, session, _id=None, name=None, nodedir=None, bootsh="boot.sh", start=True, image=None):
        """
        Create a DockerNode instance.

        :param core.emulator.session.Session session: core session instance
        :param int _id: object id
        :param str name: object name
        :param str nodedir: node directory
        :param str bootsh: boot shell to use
        :param bool start: start flag
        :param str image: image to start container with
        """
        if image is None:
            image = "ubuntu"
        self.image = image
        super(DockerNode, self).__init__(session, _id, name, nodedir, bootsh, start)

    def alive(self):
        """
        Check if the node is alive.

        :return: True if node is alive, False otherwise
        :rtype: bool
        """
        return self.client.is_alive()

    def startup(self):
        """
        Start a new namespace node by invoking the vnoded process that
        allocates a new namespace. Bring up the loopback device and set
        the hostname.

        :return: nothing
        """
        with self.lock:
            if self.up:
                raise ValueError("starting a node that is already up")
            self.makenodedir()
            self.client = DockerClient(self.name, self.image)
            self.pid = self.client.create_container()
            self.up = True

    def shutdown(self):
        """
        Shutdown logic.

        :return: nothing
        """
        # nothing to do if node is not up
        if not self.up:
            return

        with self.lock:
            self._netif.clear()
            self.client.stop_container()
            self.up = False

    def cmd(self, args, wait=True):
        """
        Runs shell command on node, with option to not wait for a result.

        :param list[str]|str args: command to run
        :param bool wait: wait for command to exit, defaults to True
        :return: exit status for command
        :rtype: int
        """
        return self.client.cmd(args, wait)

    def cmd_output(self, args):
        """
        Runs shell command on node and get exit status and output.

        :param list[str]|str args: command to run
        :return: exit status and combined stdout and stderr
        :rtype: tuple[int, str]
        """
        return self.client.cmd_output(args)

    def check_cmd(self, args):
        """
        Runs shell command on node.

        :param list[str]|str args: command to run
        :return: combined stdout and stderr
        :rtype: str
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        status, output = self.client.cmd_output(args)
        if status:
            raise CoreCommandError(status, args, output)
        return output

    def network_cmd(self, args):
        if not self.up:
            logging.debug("node down, not running network command: %s", args)
            return 0

        status, output = self.client.ns_cmd(args)
        if status:
            raise CoreCommandError(status, args, output)
        return output

    def termcmdstring(self, sh="/bin/sh"):
        """
        Create a terminal command string.

        :param str sh: shell to execute command in
        :return: str
        """
        return "docker exec -it {name} bash".format(name=self.name)

    def privatedir(self, path):
        """
        Create a private directory.

        :param str path: path to create
        :return: nothing
        """
        logging.debug("creating node dir: %s", path)
        args = "mkdir -p {path}".format(path=path)
        self.check_cmd(args)

    def mount(self, source, target):
        """
        Create and mount a directory.

        :param str source: source directory to mount
        :param str target: target directory to create
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        logging.debug("mounting source(%s) target(%s)", source, target)
        raise Exception("not supported")

    def nodefile(self, filename, contents, mode=0o644):
        """
        Create a node file with a given mode.

        :param str filename: name of file to create
        :param contents: contents of file
        :param int mode: mode for file
        :return: nothing
        """
        logging.debug("node dir(%s) ctrlchannel(%s)", self.nodedir, self.ctrlchnlname)
        logging.debug("nodefile filename(%s) mode(%s)", filename, mode)
        file_path = os.path.join(self.nodedir, filename)
        with open(file_path, "w") as f:
            os.chmod(f.name, mode)
            f.write(contents)
        self.client.copy_file(file_path, filename)

    def nodefilecopy(self, filename, srcfilename, mode=None):
        """
        Copy a file to a node, following symlinks and preserving metadata.
        Change file mode if specified.

        :param str filename: file name to copy file to
        :param str srcfilename: file to copy
        :param int mode: mode to copy to
        :return: nothing
        """
        logging.info("node file copy file(%s) source(%s) mode(%s)", filename, srcfilename, mode)
        raise Exception("not supported")
