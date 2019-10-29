# vim: set expandtab ts=4 sw=4:

# === UCSF ChimeraX Copyright ===
# Copyright 2016 Regents of the University of California.
# All rights reserved.  This software provided pursuant to a
# license agreement containing restrictions on its disclosure,
# duplication and use.  For details see:
# http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
# This notice must be embedded in or attached to all copies,
# including partial copies, of the software or any revisions
# or derivations thereof.
# === UCSF ChimeraX Copyright ===

# -----------------------------------------------------------------------------
#
def device_realsense(session, enable = None,
                     angstroms_per_meter = 50,
                     projector = False):

    di = session.models.list(type = DepthVideo)
    if enable:
        if di:
            from chimerax.core.errors import UserError
            raise UserError('RealSense camera is already enabled as model #%s'
                            % di[0].id_string)

        di = DepthVideo('RealSense camera', session,
                        depth_scale = angstroms_per_meter,
                        use_ir_projector = projector)
        session.models.add([di])
    elif enable is None:
        if di:
            msg = 'RealSense camera model #%s' % (di[0].id_string,)
        else:
            msg = 'RealSense camera is not on'
        session.logger.info(msg)
    else:
        session.models.close(di)
        print ('closed RealSense camera', len(di))
            
# -----------------------------------------------------------------------------
#
def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, BoolArg, FloatArg
    desc = CmdDesc(optional = [('enable', BoolArg)],
                   keyword = [('angstroms_per_meter', FloatArg)],
                   synopsis = 'Turn on RealSense camera rendering')
    register('device realsense', desc, device_realsense, logger=logger)
            
# -----------------------------------------------------------------------------
#
from chimerax.core.models import Model
class DepthVideo (Model):
    skip_bounds = True
    def __init__(self, name, session,
                 depth_scale = 50,	# Angstroms per meter.
                 use_ir_projector = False  # Interferes with Vive VR tracking
    ):
        Model.__init__(self, name, session)

        # With VR camera depth scale is taken from camera.
        self._depth_scale = depth_scale		# Angstroms per meter.

        self._first_image = True
        self._render_field_of_view = 69.4	# TODO: Get this from chimerax camera
        self._realsense_color_field_of_view = (69.4,42.5) # TODO: Get this from pyrealsense
        self._realsense_depth_field_of_view = (91.2,65.5) # TODO: Get this from pyrealsense
        self._use_ir_projector = use_ir_projector
        self._pipeline_started = False
        self._frames_per_second = 30	# RealSense frame rate: 30, 15, 6 at depth 1280x720, or 60,90 at 848x480
                                        #  6,15,30 at color 1920x1080, 60 at 1280x720
        self._skip_frames = 2   	# Skip updating realsense on some graphics updates
        self._current_frame = 0
        
        t = session.triggers.add_handler('graphics update', self._update_image)
        self._update_trigger = t

        self._start_video()

    def delete(self):
        raise RuntimeError('Deleted real sense')
        print ('deleted realsense camera')
        t = self._update_trigger
        if t:
            self.session.triggers.remove_handler(t)
            self._update_trigger = None

        p = self.pipeline
        if p:
            if self._pipeline_started:
                p.stop()
            self.pipeline = None
            
        Model.delete(self)
        
    def _start_video(self):
        # Configure depth and color streams
        import pyrealsense2 as rs
        self.pipeline = rs.pipeline()
        self.config = config = rs.config()
        fps = self._frames_per_second
#        config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
        config.enable_stream(rs.stream.depth, 1280, 720, rs.format.z16, fps)
#        config.enable_stream(rs.stream.color, 640, 480, rs.format.rgb8, fps)
        config.enable_stream(rs.stream.color, 960, 540, rs.format.rgb8, fps)
        pipeline_profile = self.pipeline.start(config)
        device = pipeline_profile.get_device()
        dsensor = device.first_depth_sensor()
        if dsensor.supports(rs.option.emitter_enabled):
            enable = 1 if self._use_ir_projector else 0
            dsensor.set_option(rs.option.emitter_enabled, enable) # Turn on/off IR projector
        self._pipeline_started = True

        # Setup aligning depth images to color images
        align_to = rs.stream.color
        self.align = rs.align(align_to)

    def _update_image(self, tname, view):

        if not self.display:
            if self._pipeline_started:
                # Stop video processing if not displayed.
                self.pipeline.stop()
                self._pipeline_started = False
            return False
        elif not self._pipeline_started:
            # Restart video processing when displayed.
            self.pipeline.start(self.config)
            self._pipeline_started = True

        skip = self._skip_frames
        if skip > 0:
            self._current_frame += 1
            if self._current_frame % skip != 1:
                return

        import pyrealsense2 as rs
        '''
        frames = rs.composite_frame(rs.frame())
        if self.pipeline.poll_for_frames(frames) == 0:
            return
        '''
        frames = self.pipeline.poll_for_frames()
        if frames.size() != 2:  # Got depth and color stream
            return

        
        # Wait for a coherent pair of frames: depth and color
        # This blocks if frames not available.
        # frames = self.pipeline.wait_for_frames()

        # Align the depth frame to color frame
        # TODO: Alignment is slow causing stuttering in VR.  Interpolate aligned depth
        #       values on GPU by scaling texture coordinate.
#        aligned_frames = self.align.process(frames)
        aligned_frames = frames

        depth_frame = aligned_frames.get_depth_frame()
        color_frame = aligned_frames.get_color_frame()
        if not depth_frame or not color_frame:
            return

#        if not self._first_image:
#            return	# Test if texture load is slowing VR

        import numpy
        # Convert images to numpy arrays
#        depth_image = numpy.asanyarray(depth_frame.get_data())[::-1,:]
#        color_image = numpy.asanyarray(color_frame.get_data())[::-1,:,:]
        depth_image = numpy.asanyarray(depth_frame.get_data())
        color_image = numpy.asanyarray(color_frame.get_data())
        if view.frame_number % 100 == -1:
            print ('depth', depth_image.dtype, depth_image.shape,
                   'color', color_image.dtype, color_image.shape)
            print ('depth values')
            for r in range(10):
                print(' '.join('%5d' % d for d in depth_image[230+r, 310:320]))

        if self._first_image:
            self._create_textures_video(color_image, depth_image)
            self._first_image = False
            ci = color_frame.profile.as_video_stream_profile().intrinsics
            print('color intrinsics', ci)
            cfov = rs.rs2_fov(ci)
            print('color fov', cfov)
            self._realsense_color_field_of_view = cfov
            di = depth_frame.profile.as_video_stream_profile().intrinsics
            print('depth intrinsics', di)
            dfov = rs.rs2_fov(di)
            print('depth fov', dfov)
            self._realsense_depth_field_of_view = dfov
            print('extrinsics color to depth', color_frame.profile.get_extrinsics_to(depth_frame.profile))
        else:
            self.texture.reload_texture(color_image)
            self._depth_texture.reload_texture(depth_image)

        self.redraw_needed()

    def _create_textures_video(self, color_image, depth_image):
        # TODO: Does not have sensible bounds.  Bounds don't really make sense.
        #       Causes surprises if it is the first model opened.
        from chimerax.core.graphics.drawing import rgba_drawing
        rgba_drawing(self, color_image, (-1, -1), (2, 2))
        # Invert y-axis by flipping texture coordinates
        self.texture_coordinates[:,1] = 1 - self.texture_coordinates[:,1]
        from chimerax.core.graphics import Texture
        self._depth_texture = dt = Texture(depth_image)
        # Shader wants to handle 0 depth values (= unknown depth) as max distance
        # so need to turn off linear interpolation so fragment shader gets 0 values.
        dt.linear_interpolation = False
        print ('color image type', color_image.dtype, color_image.shape)
        print ('depth image type', depth_image.dtype, depth_image.shape,
               'mean', depth_image.mean(), 'min', depth_image.min(), 'max', depth_image.max())

    def _create_textures_test(self):
        w = h = 512
        w1,h1,w2,h2 = w//4, h//4, 3*w//4, 3*h//4
        from numpy import empty, uint8, float32, uint16
        color = empty((h,w,4), uint8)
        color[:] = 255
        color[h1:h2,w1:w2,0] = 0
        #    depth = empty((h,w), float32)
        #    depth[:] = 0.5
        #    depth[h1:h2,w1:w2] = 1.0
        depth = empty((h,w), uint16)
        depth[:] = 32000
        depth[h1:h2,w1:w2] = 64000
        from chimerax.core.graphics.drawing import rgba_drawing
        rgba_drawing(self, color, (-1, -1), (2, 2))
        from chimerax.core.graphics import Texture
        self._depth_texture = Texture(depth)
         
    def delete(self):
        Model.delete(self)	# Do this first so opengl context made current
        self._depth_texture.delete_texture()
        self._depth_texture = None
        
    def draw(self, renderer, draw_pass):
        '''Render a color and depth texture pair.'''
        if self._first_image:
            return
        if not getattr(renderer, 'mix_video', True):
            return
        draw = ((draw_pass == self.OPAQUE_DRAW_PASS and self.opaque_texture)
                or (draw_pass == self.TRANSPARENT_DRAW_PASS and not self.opaque_texture))
        if not draw:
            return

        r = renderer
        r.disable_shader_capabilities(r.SHADER_LIGHTING |
                                      r.SHADER_STEREO_360 |	# Avoid geometry shift
                                      r.SHADER_DEPTH_CUE |
                                      r.SHADER_SHADOW |
                                      r.SHADER_MULTISHADOW |
                                      r.SHADER_CLIP_PLANES)
        r.enable_capabilities |= r.SHADER_DEPTH_TEXTURE

        # If the desired field of view of the texture does not match the camera field of view
        # then adjust projection size.  Also if the apect ratio of the target framebuffer and
        # the aspect ratio of the texture don't match adjust the projection size.
        w,h = r.render_size()
        fx = self._render_field_of_view
        rsfx, rsfy = self._realsense_color_field_of_view
        from math import atan, radians
        rw = atan(radians(fx/2))
        rh = rw*h/w
        rsw, rsh = atan(radians(rsfx/2)), atan(radians(rsfy/2))
        sx, sy =  rsw/rw, rsh/rh
        
        cur_proj = r.current_projection_matrix
        r.set_projection_matrix(((sx, 0, 0, 0), (0, sy, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))

        from chimerax.core.geometry import place
        p0 = place.identity()
        cur_view = r.current_view_matrix
        r.set_view_matrix(p0)
        r.set_model_matrix(p0)

        t = self._depth_texture
        t.bind_texture(r.depth_texture_unit)
        frm = 2**16 / 1000  # Realsense full range in meters (~65).
        c = self.session.main_view.camera
        from chimerax.vive.vr import SteamVRCamera
        if isinstance(c, SteamVRCamera):
            # Scale factor from RealSense depth texture 0-1 range
            # (~65 meters) to scene units (typically Angstroms).
            depth_scale = frm / c.scene_scale
        else:
            depth_scale = self._depth_scale * frm
        from math import tan, radians
        cxfov, cyfov = self._realsense_color_field_of_view
        dxfov, dyfov = self._realsense_depth_field_of_view
        dxscale = tan(radians(0.5*cxfov)) / tan(radians(0.5*dxfov))
        dyscale = tan(radians(0.5*cyfov)) / tan(radians(0.5*dyfov))
        r.set_depth_texture_parameters(dxscale, dyscale, depth_scale)
#        if r.frame_number % 200 == 1:
#            print ('depth params', dxscale, dyscale, depth_scale)
        Model.draw(self, r, draw_pass)

        # Restore view and projection matrices since drawings are not supposed to change these.
        r.set_projection_matrix(cur_proj)
        r.set_view_matrix(cur_view)
        
        r.enable_capabilities &= ~r.SHADER_DEPTH_TEXTURE
        r.disable_shader_capabilities(0)
