"""Avahi browser class for dicovery"""

import logging
import os
import optparse
import sys

import avahi
import dbus
from dbus import DBusException
import dbus.glib

from . import names as avahi_discover_names

logger = logging.getLogger(__name__)


class Browser(object):
    """Avahi browser class"""

    def get_ifprotodom_name(self, interface, protocol, domain):
        """Simple shortcut"""
        return avahi_discover_names.get_ifprotodom_name(interface, protocol, domain, avahi_server=self.server)

    def __init__(self, browse_local=True, browse_avahi_domains=True, domains=None):
        """Initialise with maybe a list of additionnal domains"""
        self.known_iface_proto_domains = set()
        self.avahi_domain_browsers = {}
        self.avahi_service_type_browsers = {}
        self.avahi_service_browsers = {}

        try:
            self.bus = dbus.SystemBus()
            self.server = dbus.Interface(self.bus.get_object(avahi.DBUS_NAME, avahi.DBUS_PATH_SERVER), avahi.DBUS_INTERFACE_SERVER)
        except Exception as e:
            logger.fatal("Failed to connect to Avahi Server (Is it running?): {}".format(e))
            raise

         # Explicitly browse .local
        if browse_local:
            self.new_domain(avahi.IF_UNSPEC, avahi.PROTO_UNSPEC, "local")

        # Browse for other browsable domains provided by Avahi
        if browse_avahi_domains:
            self.new_domain(avahi.IF_UNSPEC, avahi.PROTO_UNSPEC, '')

        # Browse other domains
        if domains:
            for domain in domains:
                self.new_domain(avahi.IF_UNSPEC, avahi.PROTO_UNSPEC, domain)

    def new_domain(self, interface, protocol, domain, flags=None):
        """Add a new domain and launch a new browse if it didn't exist"""
        key = (interface, protocol, domain)
        if key in self.known_iface_proto_domains:
            logger.debug("Don't browse twice domain {}".format(self.get_ifprotodom_name(*key)))
            return

        assert key not in self.avahi_service_type_browsers
        assert key not in self.avahi_domain_browsers

        if domain:
            logger.info("Add domain {}".format(self.get_ifprotodom_name(*key)))
            # Call new_domain hook, if domain is not empty
            if hasattr(self, 'on_new_domain'):
                self.on_new_domain(interface, protocol, domain, flags)

            # Browse service types
            b = self.server.ServiceTypeBrowserNew(interface, protocol, domain, dbus.UInt32(0))
            b = dbus.Interface(self.bus.get_object(avahi.DBUS_NAME, b), avahi.DBUS_INTERFACE_SERVICE_TYPE_BROWSER)
            b.connect_to_signal('ItemNew', self.new_service_type)
            self.avahi_service_type_browsers[key] = b

        # Browse subdomains
        db = self.server.DomainBrowserNew(interface, protocol, domain, avahi.DOMAIN_BROWSER_BROWSE, dbus.UInt32(0))
        db = dbus.Interface(self.bus.get_object(avahi.DBUS_NAME, db), avahi.DBUS_INTERFACE_DOMAIN_BROWSER)
        db.connect_to_signal('ItemNew', self.new_domain)
        self.avahi_domain_browsers[key] = db
        self.known_iface_proto_domains.add(key)

    def new_service_type(self, interface, protocol, stype, domain, flags):
        """Add a new service type"""
        key = (interface, protocol, stype, domain)
        if key in self.avahi_service_browsers:
            logger.debug("Don't browse twice service type '{}' in domain {}".format(stype, self.get_ifprotodom_name(interface, protocol, domain)))
            return

        logger.debug("Browsing for services of type '{}' in domain {}".format(stype, self.get_ifprotodom_name(interface, protocol, domain)))
        if hasattr(self, 'on_new_service_type'):
            self.on_new_service_type(interface, protocol, stype, domain, flags)

        b = self.server.ServiceBrowserNew(interface, protocol, stype, domain, dbus.UInt32(0))
        b = dbus.Interface(self.bus.get_object(avahi.DBUS_NAME, b),  avahi.DBUS_INTERFACE_SERVICE_BROWSER)
        b.connect_to_signal('ItemNew', self.new_service)
        b.connect_to_signal('ItemRemove', self.remove_service)
        self.avahi_service_browsers[key] = b

    def new_service(self, interface, protocol, name, stype, domain, flags):
        """Add a new service"""
        logger.info("Found service '{}' of type '{}' in domain {}".format(name, stype, self.get_ifprotodom_name(interface, protocol, domain)))
        if hasattr(self, 'on_new_service'):
            self.on_new_service(interface, protocol, name, stype, domain, flags)

    def remove_service(self, interface, protocol, name, stype, domain, flags):
        logger.info("Service '{}' of type '{}' in domain {} disappeared".format(name, stype, self.get_ifprotodom_name(interface, protocol, domain)))
        if hasattr(self, 'on_remove_service'):
            self.on_new_service(interface, protocol, name, stype, domain, flags)
