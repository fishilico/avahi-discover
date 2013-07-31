"""Entry point"""

import gtk
import logging
import optparse

from . import browser, gui


def main(loglevel=None):
    log_handler = logging.StreamHandler()
    log_handler.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))
    root_logger = logging.getLogger()
    root_logger.setLevel(loglevel if loglevel is not None else logging.INFO)
    root_logger.addHandler(log_handler)

    parser = optparse.OptionParser(usage="usage: %prog [options]")
    parser.add_option('-d', '--domain', action='store', dest='domain', help='use this domain', metavar="DOMAIN")
    (options, args) = parser.parse_args()
    main_window = gui.MainWindow(domains=options.domain)
    gtk.main()
