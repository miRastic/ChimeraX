# vim: set expandtab shiftwidth=4 softtabstop=4:
"""
nogui: Text UI
==============

Text-based user interface.  API-compatible with :py:module:`ui` package.
"""
from ..tasks import Task
from ..logger import PlainTextLog
_color_output = False

_log_level = {
        PlainTextLog.LEVEL_INFO: 'info',
        PlainTextLog.LEVEL_WARNING: 'warning',
        PlainTextLog.LEVEL_ERROR: 'error',
}

_colors = {
        "info": "",
        "warning": "",
        "error": "",
        "status": "",
        "normal": "",
        "background": "",
        "prompt": "",
        "endprompt": "",
}


class NoGuiLog(PlainTextLog):

    def log(self, level, msg):
        level_name = _log_level[level]
        print("%s%s: %s%s" % (
            _colors[level_name], level_name, msg, _colors["normal"]), end='')
        return True

    def status(self, msg, color, secondary):
        if secondary:
            return False
        if msg:
            print("%sstatus: %s%s" % (
                _colors["status"], msg, _colors["normal"]))
        return True


class UI:

    def __init__(self, session):
        global _color_output
        self.is_gui = False
        session.logger.add_log(NoGuiLog())
        import weakref
        self._session = weakref.ref(session)
        self._queue = None
        import sys
        if sys.stdout.isatty():
            try:
                import colorama
                colorama.init()
                _color_output = True
                _colors["info"] = colorama.Fore.GREEN
                _colors["warning"] = colorama.Fore.YELLOW
                _colors["error"] = colorama.Fore.RED
                _colors["status"] = colorama.Fore.MAGENTA
                _colors["normal"] = colorama.Fore.WHITE
                _colors["background"] = colorama.Back.BLACK
                _colors["prompt"] = colorama.Fore.BLUE + colorama.Style.BRIGHT
                _colors["endprompt"] = colorama.Style.NORMAL + _colors["normal"]
            except ImportError:
                pass

        if not self.initialize_offscreen_rendering(session.main_view):
            session.logger.info('Offscreen rendering not available')

    def initialize_offscreen_rendering(self, view):
        from .. import graphics
        try:
            c = graphics.OffScreenRenderingContext()
        except:
            c = None             # OSMesa library was not found
        if c:
            view.initialize_context(c)
        return not c is None

    def splash_info(self, message, splash_step, num_splash_steps):
        import sys
        print("%.2f%% done: %s" % (splash_step / num_splash_steps * 100,
                                   message), file=sys.stderr)

    def build(self):
        pass  # nothing to build

    def quit(self):
        import os
        import sys
        session = self._session()  # resolve back reference
        session.logger.status("Exiting ...", blank_after=0)
        session.logger.clear()   # Clear logging timers
        sys.exit(os.EX_OK)

    def event_loop(self):
        from queue import Queue
        self._queue = Queue()
        session = self._session()  # resolve back reference
        input = _Input(session)
        input.start()
        from ..tasks import FINISHED, TERMINATED
        while input.state not in [FINISHED, TERMINATED]:
            func, args, kw = self._queue.get()
            try:
                func(*args, **kw)
            finally:
                self._queue.task_done()

    def thread_safe(self, func, *args, **kw):
        if self._queue:
            self._queue.put((func, args, kw))
        else:
            func(*args, **kw)


class _Input(Task):

    SESSION_ENDURING = True
    SESSION_SKIP = True

    def __init__(self, session):
        # Initializer, runs in UI thread
        super().__init__(session)
        from ..commands import Command
        self._cmd = Command(session)
        from threading import Semaphore
        self._sem = Semaphore()

    def run(self):
        # Actual event loop, runs in our own thread
        # Schedules calls to self.execute in UI thread
        prompt = 'cmd> '
        if _color_output:
            prompt = _colors["prompt"] + prompt + _colors["endprompt"]
        ui = self.session.ui
        while True:
            try:
                self._sem.acquire()
                text = input(prompt)
                ui.thread_safe(self.run_command, text)
            except EOFError:
                # Need to get UI thread to do something
                # in order to detect termination of input thread
                ui.thread_safe(print, "EOF")
                self.session.logger.clear()
                break

    def run_command(self, text):
        # Run command from input queue, runs in UI thread
        # Separate from "execute" to handle input synchronization
        self.execute(text)
        self._sem.release()

    def execute(self, text):
        # Command execution, runs in UI thread
        from .. import errors
        text = text.strip()
        if not text:
            return
        logger = self.session.logger
        try:
            self._cmd.run(text)
        except errors.UserError as err:
            rest = self._cmd.current_text[self._cmd.amount_parsed:]
            spaces = len(rest) - len(rest.lstrip())
            error_at = self._cmd.amount_parsed + spaces
            syntax_error = error_at < len(self._cmd.current_text)
            if syntax_error:
                error_at -= self._cmd.start
                logger.error(self._cmd.current_text[self._cmd.start:])
                if error_at:
                    logger.error("%s^" % ('.' * error_at))
            logger.error(str(err))
        except Exception:
            logger.error("\nUnexpected exception, save your work and exit:\n")
            import traceback
            logger.error(traceback.format_exc())

    #
    # Required State methods, do nothing
    #
    def reset_state(self, session):
        pass

    def take_snapshot(self, session, flags):
        return

    def restore_snapshot(self, session, bundle_info, version, data):
        pass
