from .qt import QtCore, QtGui

class Mouse_Modes:

    def __init__(self, view):

        self.view = view
        self.mouse_modes = {}
        self.mouse_down_position = None
        self.last_mouse_position = None
        self.last_mouse_time = None
        self.mouse_pause_interval = 0.5         # seconds
        self.mouse_pause_position = None
        self.mouse_perimeter = False
        self.wheel_function = None
        self.bind_standard_mouse_modes()

        self.move_selected = False

        view.mousePressEvent = self.mouse_press_event
        view.mouseMoveEvent = self.mouse_move_event
        view.mouseReleaseEvent = self.mouse_release_event
        view.wheelEvent = self.wheel_event
        view.touchEvent = self.touch_event

        self.trackpad_speed = 4         # Trackpad position scaling to match mouse position sensitivity
        view.add_new_frame_callback(self.collapse_touch_events)
        self.recent_touch_points = None

    # Button is "left", "middle", or "right"
    def bind_mouse_mode(self, button, mouse_down,
                        mouse_drag = None, mouse_up = None):
        self.mouse_modes[button] = (mouse_down, mouse_drag, mouse_up)
        
    def mouse_press_event(self, event):
        self.dispatch_mouse_event(event, 0)
    def mouse_move_event(self, event):
        self.dispatch_mouse_event(event, 1)
    def mouse_release_event(self, event):
        self.dispatch_mouse_event(event, 2)
    def wheel_event(self, event):
        if self.is_trackpad_wheel_event(event):
            return
        f = self.wheel_function
        if f:
            f(event)

    def is_trackpad_wheel_event(self, event):
        # Suppress trackpad wheel events when using multitouch
        # Ignore scroll events generated by the Mac trackpad (2-finger drag).
        # There seems to be no reliable way to tell if a scroll came from the trackpad.
        # Scrolls from the Apple Magic Mouse look like a trackpad scroll.
        # Only way to tell true trackpad events seems to be to look at trackpad touches.
        if getattr(self, 'last_trackpad_touch_count', 0) >= 2:
            return True # Ignore trackpad generated scroll
        if hasattr(self, 'last_trackpad_touch_time'):
            import time
            if time.time() < self.last_trackpad_touch_time + 1.0:
                # Suppress momentum scrolling for 1 second after trackpad scrolling ends.
                return True
        return False
        
    def dispatch_mouse_event(self, event, fnum):

        b = self.event_button_name(event)
        f = self.mouse_modes.get(b)
        if f and f[fnum]:
            f[fnum](event)

    def event_button_name(self, event):

        # button() gives press/release button, buttons() gives move buttons
        b = event.button() | event.buttons()
        if b & QtCore.Qt.LeftButton:
            m = event.modifiers()
            if m == QtCore.Qt.AltModifier:
                bname = 'middle'
            elif m == QtCore.Qt.ControlModifier:
                # On Mac the Command key produces the Control modifier
                # and it is documented in Qt to behave that way.  Yuck.
                bname = 'right'
            else:
                bname = 'left'
        elif b & QtCore.Qt.MiddleButton:
            bname = 'middle'
        elif b & QtCore.Qt.RightButton:
            bname = 'right'
        else:
            bname = None
        return bname

    def bind_standard_mouse_modes(self, buttons = ['left', 'middle', 'right', 'wheel']):
        modes = (
            ('left', self.mouse_down, self.mouse_rotate, self.mouse_up_select),
            ('right', self.mouse_down, self.mouse_translate, self.mouse_up),
            ('middle', self.mouse_down, self.mouse_contour_level, self.mouse_up),
            )
        for m in modes:
            if m[0] in buttons:
                self.bind_mouse_mode(*m)
        if 'wheel' in buttons:
            self.wheel_function = self.wheel_zoom

    def mouse_down(self, event):
        w,h = self.view.window_size
        cx, cy = event.x()-0.5*w, event.y()-0.5*h
        fperim = 0.9
        self.mouse_perimeter = (abs(cx) > fperim*0.5*w or abs(cy) > fperim*0.5*h)
        self.mouse_down_position = event.pos()
        self.remember_mouse_position(event)

    def mouse_up(self, event):
        self.mouse_down_position = None
        self.last_mouse_position = None

    def mouse_up_select(self, event):
        if event.pos() == self.mouse_down_position:
            self.mouse_select(event)
        self.mouse_down_position = None
        self.last_mouse_position = None

    def remember_mouse_position(self, event):
        self.last_mouse_position = event.pos()

    def mouse_pause_tracking(self):
        v = self.view
        cp = v.mapFromGlobal(QtGui.QCursor.pos())
        w,h = v.window_size
        x,y = cp.x(), cp.y()
        if x < 0 or y < 0 or x >= w or y >= h:
            return      # Cursor outside of graphics window
        from time import time
        t = time()
        mp = self.mouse_pause_position
        if cp == mp:
            lt = self.last_mouse_time
            if lt and t >= lt + self.mouse_pause_interval:
                self.mouse_pause()
                self.mouse_pause_position = None
                self.last_mouse_time = None
            return
        self.mouse_pause_position = cp
        if mp:
            # Require mouse move before setting timer to avoid
            # repeated mouse pause callbacks at same point.
            self.last_mouse_time = t

    def mouse_pause(self):
        v = self.view
        if v.session.main_window.showing_graphics():
            lp = self.mouse_pause_position
            f, p = v.first_intercept(lp.x(), lp.y())
            if p:
                v.session.show_status('Mouse over %s' % p.description())
            # TODO: Clear status if it is still showing mouse over message but mouse is over nothing.
            #      Don't want to clear a different status message, only mouse over message.

    def mouse_motion(self, event):
        lmp = self.last_mouse_position
        if lmp is None:
            dx = dy = 0
        else:
            dx = event.x() - lmp.x()
            dy = event.y() - lmp.y()
            # dy > 0 is downward motion.
        self.remember_mouse_position(event)
        return dx, dy

    def mouse_rotate(self, event):

        axis, angle = self.mouse_rotation(event)
        self.rotate(axis, angle)

    def rotate(self, axis, angle):

        v = self.view
        # Convert axis from camera to scene coordinates
        saxis = v.camera.view().apply_without_translation(axis)
        v.rotate(saxis, angle, self.models())

    def models(self):
        if self.move_selected:
            m = self.view.session.selected_models()
            if len(m) == 0:
                m = None
        else:
            m = None
        return m

    def mouse_rotation(self, event):

        dx, dy = self.mouse_motion(event)
        import math
        angle = 0.5*math.sqrt(dx*dx+dy*dy)
        if self.mouse_perimeter:
            # z-rotation
            axis = (0,0,1)
            w, h = self.view.window_size
            ex, ey = event.x()-0.5*w, event.y()-0.5*h
            if -dy*ex+dx*ey < 0:
                angle = -angle
        else:
            axis = (dy,dx,0)
        return axis, angle

    def mouse_translate(self, event):

        dx, dy = self.mouse_motion(event)
        self.translate((dx, -dy, 0))

    def translate(self, shift):

        psize = self.pixel_size()
        s = tuple(dx*psize for dx in shift)     # Scene units
        v = self.view
        step = v.camera.view().apply_without_translation(s)    # Scene coord system
        v.translate(step, self.models())

    def mouse_zoom(self, event):        

        dx, dy = self.mouse_motion(event)
        psize = self.pixel_size()
        v = self.view
        shift = v.camera.view().apply_without_translation((0, 0, 3*psize*dy))
        v.translate(shift)

    def wheel_zoom(self, event):        

        d = event.angleDelta().y()/120.0   # Usually one wheel click is delta of 120
        psize = self.pixel_size()
        v = self.view
        shift = v.camera.view().apply_without_translation((0, 0, 100*d*psize))
        v.translate(shift)

    def pixel_size(self, min_scene_frac = 1e-5):

        v = self.view
        psize = v.pixel_size()
        c,r = v.session.bounds_center_and_width()
        psize = max(psize, r*min_scene_frac)
        return psize

    def mouse_select(self, event):

        x,y = event.x(), event.y()
        v = self.view
        p, pick = v.first_intercept(x,y)
        ses = v.session
        toggle = bool(event.modifiers() & QtCore.Qt.ShiftModifier)
        if pick is None:
            if not toggle:
                ses.clear_selection()
                ses.show_status('cleared selection')
        else:
            if not toggle:
                ses.clear_selection()
            pick.select(toggle)
            ses.selection_changed()
        
    def mouse_contour_level(self, event):

        v = self.view
        if getattr(self, 'last_contour_frame', None) == v.frame_number:
            return # Handle only one recontour event per frame
        self.last_contour_frame = v.frame_number

        dx, dy = self.mouse_motion(event)
        f = -0.001*dy
        
        s = v.session
        mdisp = [m for m in s.maps() if m.display]
        sel = set(s.selected_models())
        msel = [m for m in mdisp if m in sel]
        models = msel if msel else mdisp
        for m in models:
            adjust_threshold_level(m, f)
            m.show()
        
    def wheel_contour_level(self, event):
        d = event.angleDelta().y()       # Usually one wheel click is delta of 120
        f = d/(120.0 * 30)
        for m in self.view.session.maps():
            if m.display:
                adjust_threshold_level(m, f)
                m.show()

    # Appears that Qt has disabled touch events on Mac due to unresolved scrolling lag problems.
    # Searching for qt setAcceptsTouchEvents shows they were disabled Oct 17, 2012.
    # A patch that allows an environment variable QT_MAC_ENABLE_TOUCH_EVENTS to allow touch
    # events had status "Review in Progress" as of Jan 16, 2013 with no more recent update.
    # The Qt 5.0.2 source code qcocoawindow.mm does not include the environment variable patch.
    def touch_event(self, event):

        t = event.type()
        if t == QtCore.QEvent.TouchUpdate:
            # On Mac touch events get backlogged in queue when the events cause 
            # time consuming computatation.  It appears Qt does not collapse the events.
            # So event processing can get tens of seconds behind.  To reduce this problem
            # we only handle one touch update per redraw.
            self.recent_touch_points = event.touchPoints()
#            self.process_touches(event.touchPoints())
        elif t == QtCore.QEvent.TouchEnd:
            self.last_trackpad_touch_count = 0
            self.recent_touch_points = None
            self.mouse_up(event = None)

    def collapse_touch_events(self):
        touches = self.recent_touch_points
        if not touches is None:
            self.process_touches(touches)
            self.recent_touch_points = None

    def process_touches(self, touches):
        min_pinch = 0.1
        n = len(touches)
        import time
        self.last_trackpad_touch_time = time.time()
        self.last_trackpad_touch_count = n
        s = self.trackpad_speed
        moves = [(id, s*(t.pos().x() - t.lastPos().x()), s*(t.pos().y() - t.lastPos().y())) for t in touches]
        if n == 2:
            (dx0,dy0),(dx1,dy1) = moves[0][1:], moves[1][1:]
            from math import sqrt, exp, atan2, pi
            l0,l1 = sqrt(dx0*dx0 + dy0*dy0),sqrt(dx1*dx1 + dy1*dy1)
            d12 = dx0*dx1+dy0*dy1
            if l0 >= min_pinch and l1 >= min_pinch and d12 < -0.7*l0*l1:
                # pinch or twist
                (x0,y0),(x1,y1) = [(p.x(), p.y()) for p in (touches[0].pos(), touches[1].pos())]
                sx,sy = x1-x0,y1-y0
                sn = sqrt(sx*sx + sy*sy)
                sd0,sd1 = sx*dx0 + sy*dy0, sx*dx1 + sy*dy1
                if abs(sd0) > 0.5*sn*l0 and abs(sd1) > 0.5*sn*l1:
                    # pinch to zoom
                    s = 1 if sd1 > 0 else -1
                    self.translate((0,0,10*s*(l0+l1)))
                    return
                else:
                    # twist
                    a = (atan2(-sy*dx1+sx*dy1,sn*sn) +
                         atan2(sy*dx0-sx*dy0,sn*sn))*180/pi
                    zaxis = (0,0,1)
                    self.rotate(zaxis, -3*a)
                    return
            dx = sum(x for id,x,y in moves)
            dy = sum(y for id,x,y in moves)
            # rotation
            from math import sqrt
            angle = 0.3*sqrt(dx*dx + dy*dy)
            if angle != 0:
                axis = (dy, dx, 0)
                self.rotate(axis, angle)
        elif n == 3:
            dx = sum(x for id,x,y in moves)
            dy = sum(y for id,x,y in moves)
            # translation
            if dx != 0 or dy != 0:
                f = self.mouse_modes.get('right')
                if f:
                    fnum = 0 if self.last_mouse_position is None else 1 # 0 = down, 1 = drag, 2 = up
                    e = self.trackpad_event(dx,dy)
                    f[fnum](e)
                    self.remember_mouse_position(e)

    def trackpad_event(self, dx, dy):
        p = self.last_mouse_position
        if p is None:
            v = self.view
            cp = v.mapFromGlobal(QtGui.QCursor.pos())
            x,y = cp.x(),cp.y()
        else:
            x,y = p.x()+dx, p.y()+dy
        class Trackpad_Event:
            def __init__(self,x,y):
                self._x, self._y = x,y
            def x(self):
                return self._x
            def y(self):
                return self._y
            def pos(self):
                return QtCore.QPoint(self._x,self._y)
        e = Trackpad_Event(x,y)
        return e

def adjust_threshold_level(m, f):
    ms = m.matrix_value_statistics()
    step = f * (ms.maximum - ms.minimum)
    if m.representation == 'solid':
        new_levels = [(l+step,b) for l,b in m.solid_levels]
        l,b = new_levels[-1]
        new_levels[-1] = (max(l,1.01*ms.maximum),b)
        m.set_parameters(solid_levels = new_levels)
    else:
        new_levels = tuple(l+step for l in m.surface_levels)
        m.set_parameters(surface_levels = new_levels)
