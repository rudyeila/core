#!/usr/bin/python
#
# run iperf to measure the effective throughput between two nodes when
# n nodes are connected to a virtual wlan; run test for testsec
# and repeat for minnodes <= n <= maxnodes with a step size of
# nodestep

import datetime
import parser
from builtins import range

from core import load_logging_config
from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import IpPrefixes
from core.emulator.enumerations import EventTypes, NodeTypes

load_logging_config()


def example(options):
    # ip generator for example
    prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")

    # create emulator instance for creating sessions and utility methods
    coreemu = CoreEmu()
    session = coreemu.create_session()

    # must be in configuration state for nodes to start, when using "node_add" below
    session.set_state(EventTypes.CONFIGURATION_STATE)

    # create switch network node
    switch = session.add_node(_type=NodeTypes.SWITCH)

    # create nodes
    for _ in range(options.nodes):
        node = session.add_node()
        interface = prefixes.create_interface(node)
        session.add_link(node.id, switch.id, interface_one=interface)

    # instantiate session
    session.instantiate()

    # get nodes to run example
    first_node = session.get_node(2)
    last_node = session.get_node(options.nodes + 1)

    print("starting iperf server on node: %s" % first_node.name)
    first_node.cmd(["iperf", "-s", "-D"])
    first_node_address = prefixes.ip4_address(first_node)
    print("node %s connecting to %s" % (last_node.name, first_node_address))
    last_node.client.icmd(["iperf", "-t", str(options.time), "-c", first_node_address])
    first_node.cmd(["killall", "-9", "iperf"])

    # shutdown session
    coreemu.shutdown()


def main():
    options = parser.parse_options("switch")

    start = datetime.datetime.now()
    print("running switch example: nodes(%s) time(%s)" % (options.nodes, options.time))
    example(options)
    print("elapsed time: %s" % (datetime.datetime.now() - start))


if __name__ == "__main__":
    main()
