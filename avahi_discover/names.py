"""Functions to handle interface, protocol, domain and type names and stringify them"""

import avahi
import avahi.ServiceTypeDatabase

service_type_db = avahi.ServiceTypeDatabase.ServiceTypeDatabase()


def get_proto_name(protocol):
    if protocol == avahi.PROTO_INET:
        return 'IPv4'
    if protocol == avahi.PROTO_INET6:
        return 'IPv6'
    if protocol < 0:
        return 'n/a'
    return 'unk_proto_' + str(protocol)


def get_if_name(interface, avahi_server=None):
    if interface <= 0:
        return 'n/a'
    elif avahi_server is not None:
        return avahi_server.GetNetworkInterfaceNameByIndex(interface)
    else:
        return 'iface_' + str(interface)


def get_ifproto_name(interface, protocol, avahi_server=None):
    if interface == avahi.IF_UNSPEC and protocol == avahi.PROTO_UNSPEC:
        return 'Wide Area'
    else:
        return get_if_name(interface, avahi_server=avahi_server) + " " + get_proto_name(protocol)


def get_ifprotodom_name(interface, protocol, domain, avahi_server=None):
    if interface <= 0 and protocol <= 0:
        return domain
    else:
        return domain + ' on ' + get_ifproto_name(interface, protocol, avahi_server=avahi_server)


def get_service_type_name(stype):
    try:
        return service_type_db[stype]
    except KeyError:
        return stype
