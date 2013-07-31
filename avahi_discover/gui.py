"""Graphical user interface of Avahi Discover"""

import logging
import os.path

import avahi
import dbus
import gobject
import gtk

from . import browser
from . import names

logger = logging.getLogger(__name__)

try:
    import gettext
    gettext.bindtextdomain("avahi", "/usr/share/locale")
    gettext.textdomain("avahi")
    _ = gettext.gettext
    del gettext
except Exception, e:
    # Fallback to identity
    logger.warning("Failed to initialize internationalization: {}".format(e))
    _ = lambda x: x


class MainWindow(browser.Browser):
    """Main window class"""

    def __init__(self, ui_file="avahi-discover.ui", **kwargs):
        ui_path = os.path.join(os.path.dirname(__file__), ui_file)
        gtk.window_set_default_icon_name("network-wired")
        self.ui = gtk.Builder()
        self.ui.add_from_file(ui_path)
        self.ui.connect_signals(self)
        self.tree_view = self.ui.get_object("tree_view")
        self.info_label = self.ui.get_object("info_label")
        self.treemodel = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING)
        self.tree_view.set_model(self.treemodel)
        #creating the columns headers
        self.tree_view.set_headers_visible(False)
        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn("", renderer, text=0)
        column.set_resizable(True)
        column.set_sizing("GTK_TREE_VIEW_COLUMN_GROW_ONLY")
        column.set_expand(True)
        self.tree_view.append_column(column)

        # Tree domain -> type -> service
        self.domain_iters = {}
        self.type_iters = {}
        self.service_iters = {}
        super(MainWindow, self).__init__(**kwargs)

        # Some "improvements"
        # Don't unfold .local if there are other domains
        self.unfold_local = True

    @staticmethod
    def gtk_main_quit(*args):
        gtk.main_quit()

    def on_tree_view_cursor_changed(self, widget, *args):
        (model, treeiter) = widget.get_selection().get_selected()
        stype = None
        if treeiter is not None:
            (name, interface, protocol, stype, domain) = self.treemodel.get(treeiter, 1, 2, 3, 4, 5)
        if stype is None:
            self.info_label.set_markup(_("<i>No service currently selected.</i>"))
            return
        #Asynchronous resolving
        self.server.ResolveService(int(interface), int(protocol), name, stype, domain, avahi.PROTO_UNSPEC, dbus.UInt32(0),
                                   reply_handler=self.service_resolved, error_handler=self.print_error)

    def print_error(self, err):
        self.info_label.set_markup("<b>Error:</b> " + str(err))
        logger.error(err)

    def service_resolved(self, interface, protocol, name, stype, domain, host, aprotocol, address, port, txt, flags):
        logger.info("Service data for service '{}' of type '{}' in domain {}:".format(name, stype, names.get_ifprotodom_name(interface, protocol, domain, avahi_server=self.server)))
        logger.info("   Host {} ({}) port {}, TXT data: {}".format(host, address, port, str(avahi.txt_array_to_string_array(txt))))
        self.update_label(interface, protocol, name, stype, domain, host, aprotocol, address, port, avahi.txt_array_to_string_array(txt))

    def update_label(self, interface, protocol, name, stype, domain, host, aprotocol, address, port, txt):
        txts = []
        if len(txt) != 0:
            for el in txt:
                if '=' not in el:
                    txts.append("<b>" + _("TXT") + " <i>" + el + "</i></b>")
                else:
                    k, v = el.split('=', 1)
                    txts.append("<b>" + _("TXT") + " <i>" + k + "</i></b> = " + v)
        else:
            txts = ["<b>" + _("TXT Data:") + "</b> <i>" + _("empty") + "</i>"]

        infos = "<b>" + _("Service Type:") + "</b> {}\n".format(stype)
        infos += "<b>" + _("Service Name:") + "</b> {}\n".format(name)
        infos += "<b>" + _("Domain Name:") + "</b> {}\n".format(domain)
        infos += "<b>" + _("Interface:") + "</b> {}\n".format(names.get_ifproto_name(interface, protocol, avahi_server=self.server))
        infos += "<b>" + _("Address:") + "</b> {} / {} port {}\n".format(host, address, port)
        infos += "\n".join(txts)
        self.info_label.set_markup(infos)

    def insert_row(self, parent, content, name, interface, protocol, stype, domain):
        treeiter = self.treemodel.insert_after(parent, None)
        self.treemodel.set(treeiter, 0, content, 1, name, 2, str(interface), 3, str(protocol), 4, stype, 5, domain)
        return treeiter

    def get_or_create_domain_iter(self, interface, protocol, domain):
        """Get an existing domain treeiter in the treeview or create a new one"""
        key = (interface, protocol, domain)
        try:
            return self.domain_iters[key]
        except KeyError:
            pass
        domain_label = self.get_ifprotodom_name(interface, protocol, domain)

        # "local" domain special stuff
        if domain != 'local' and not domain.endswith('.local'):
            self.unfold_local = False

        # Find parent domain
        parent = None
        parent_domlen = 0
        for k, v in self.domain_iters.items():
            if interface == k[0] and protocol == k[1] and domain.endswith(k[2]) and len(k[2]) > parent_domlen:
                parent = v
                parent_domlen = len(k[2])

        # For local domain, use local-unspecified parent
        if (interface != avahi.IF_UNSPEC or protocol != avahi.PROTO_UNSPEC) and domain == 'local':
            parent = self.get_or_create_domain_iter(avahi.IF_UNSPEC,  avahi.PROTO_UNSPEC, 'local')

        treeiter = self.insert_row(parent, domain_label, None, interface, protocol, None, domain)
        self.domain_iters[key] = treeiter
        return treeiter

    def get_or_create_type_iter(self, interface, protocol, stype, domain):
        """Get an existing type treeiter in the treeview or create a new one"""
        key = (interface, protocol, stype, domain)
        try:
            return self.type_iters[key]
        except KeyError:
            pass
        type_label = names.get_service_type_name(stype)

        # Find parent treeiter, the domain
        parent = self.get_or_create_domain_iter(interface, protocol, domain)
        treeiter = self.insert_row(parent, type_label, None, interface, None, None, None)
        self.type_iters[key] = treeiter
        return treeiter

    def get_or_create_service_iter(self, interface, protocol, name, stype, domain):
        """Get an existing service treeiter in the treeview or create a new one"""
        key = (interface, protocol, name, stype, domain)
        try:
            return self.service_iters[key]
        except KeyError:
            pass

        # Find parent treeiter, the type
        parent = self.get_or_create_type_iter(interface, protocol, stype, domain)
        treeiter = self.insert_row(parent, name, name, interface, protocol, stype, domain)
        self.service_iters[key] = treeiter
        return treeiter

    def on_new_domain(self, interface, protocol, domain, flags):
        # Don't create a new domain for local with unspecified protocol/domain
        if interface == avahi.IF_UNSPEC and protocol == avahi.PROTO_UNSPEC and domain == 'local':
            return
        self.get_or_create_domain_iter(interface, protocol, domain)

    def on_new_service(self, interface, protocol, name, stype, domain, flags):
        treeiter = self.get_or_create_service_iter(interface, protocol, name, stype, domain)
        # expand the tree of this path
        if self.unfold_local or (domain != 'local' and not domain.endswith('.local')):
            self.tree_view.expand_to_path(self.treemodel.get_path(treeiter))

    def on_remove_service(self, interface, protocol, name, stype, domain, flags):
        self.info_label.set_markup("")
        treeiter = None

        # Remove service treeiter
        try:
            treeiter = self.service_iters[(interface, protocol, name, stype, domain)]
        except KeyError:
            logger.error("Removed service doesn't exist in tree: '{}' of type '{}' in domain {}".format(name, stype, self.get_ifprotodom_name(interface, protocol, domain)))
            return
        parent = self.treemodel.iter_parent(treeiter)
        self.treemodel.remove(treeiter)
        del self.service_iters[(interface, protocol, name, stype, domain)]
        if self.treemodel.iter_has_child(parent):
            return

        # Remove type treeiter, if empty
        try:
            treeiter = self.type_iters[(interface, protocol, stype, domain)]
        except KeyError:
            logger.error("Removed service type doesn't exist in tree: '{}' in domain {}".format(stype, self.get_ifprotodom_name(interface, protocol, domain)))
            return
        parent = self.treemodel.iter_parent(treeiter)
        self.treemodel.remove(treeiter)
        del self.type_iters[(interface, protocol, stype, domain)]
        if self.treemodel.iter_has_child(parent):
            return

        # Remove domain treeiter, if empty
        try:
            treeiter = self.domain_iters[(interface, protocol, domain)]
        except KeyError:
            logger.error("Removed domain doesn't exist in tree: {}".format(self.get_ifprotodom_name(interface, protocol, domain)))
            return
        parent = self.treemodel.iter_parent(treeiter)
        self.treemodel.remove(treeiter)
        del self.domain_iters[(interface, protocol, domain)]
